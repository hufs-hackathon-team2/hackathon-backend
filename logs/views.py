import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from decouple import config
from openai import OpenAI
from .models import PlusLog, Asset, PlusLogAsset

from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

#LG-02. 키워드 추출 및 에셋 매핑
client = OpenAI(api_key=config('OPENAI_API_KEY'))

ASSET_WHITELIST = {
    '스트레칭': 'floormat', '요가': 'floormat', '홈트': 'floormat',
    '산책': 'floorfootprint', '걷기': 'floorfootprint', '조깅': 'floorfootprint',
    '근력': 'floordumbbell', '웨이트': 'floordumbbell', '헬스': 'floordumbbell',
    '러닝': 'floorsneakers', '달리기': 'floorsneakers',
    '계단': 'wallstairs', '등산': 'wallstairs'
}

@require_POST
@csrf_exempt
def create_and_analyze_log(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
    
    user_id = data.get('user_id')
    cycle_id = data.get('cycle_id')
    content = data.get('content')

    if not user_id or not cycle_id or not content:
            return JsonResponse(
                {'error': 'user_id, cycle_id, content 필드가 모두 필요합니다.'}, 
                status=400
            )

    try:
        log_entry = PlusLog.objects.create(
            user_id=user_id,
            cycle_id=cycle_id,
            content=content,
            state='PENDING'
        )

        prompt = f"""
        다음 유저의 로그 내용을 분석하여, 핵심 키워드 3개를 추출해서 콤마(,)로 구분해줘.
        단, 로그 내용에 건강을 해치는 위험한 내용이 포함되어 있다면 절대로 키워드를 추출하지 말고 오직 'DANGER'라고만 응답해.
        키워드 / DANGER 이외의 다른 말은 절대로 하지 마.
            
        로그 내용: "{content}"
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "너는 유저 로그를 분석해서 키워드를 추출하는 AI야."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50
        )

        llm_result = response.choices[0].message.content.strip()

        if llm_result == 'DANGER':
            log_entry.state = 'FAILED'
            log_entry.processed_at = timezone.now()
            log_entry.save()
            return JsonResponse({'error': '위험 키워드가 포함된 경우 저장되지 않습니다.'}, status=403)

        extracted_keywords = []

        raw_keywords = [k.strip() for k in llm_result.split(',')][:3]
        for keyword in raw_keywords:
            if keyword in ASSET_WHITELIST:
                target_asset_id = ASSET_WHITELIST[keyword]

                asset, created = Asset.objects.get_or_create(
                    asset_name=target_asset_id,
                    defaults={
                        'category': '운동',
                        'image_url': f'https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/{target_asset_id}.png'
                    }
                )

                PlusLogAsset.objects.create(
                    log=log_entry,
                    asset=asset,
                    extracted_keyword=keyword
                )
                extracted_keywords.append(keyword)

        log_entry.state = 'DONE'
        log_entry.processed_at = timezone.now()
        log_entry.save()

        return JsonResponse({
            'message': '로그 분석 성공',
            'log_id': log_entry.log_id,
            'extracted_keywords': extracted_keywords
        }, status=200)

    except Exception as e:
        if 'log_entry' in locals():
            log_entry.state = 'FAILED'
            log_entry.save()
        return JsonResponse(
            {'error': '로그 처리 중 오류 발생'}, 
            status=500
            )


# LG-03. 기록 목록 조회
@require_http_methods(["GET"])
def get_log_list(request):
    try:
        page_number = request.GET.get('page', 1)
        cycle_id = request.GET.get('cycle_id')

        if not cycle_id:
            return JsonResponse({'error': 'cycle_id 파라미터가 필요합니다.'}, status=400)

        logs_query = PlusLog.objects.filter(
            cycle_id=cycle_id,
            deleted_at__isnull=True
        ).prefetch_related('pluslogasset_set').order_by('-created_at')


        paginator = Paginator(logs_query, 10)
        page_obj = paginator.get_page(page_number)

        result_logs = []
        for log in page_obj:
            keywords = [asset.extracted_keyword for asset in log.pluslogasset_set.all()]
            
            result_logs.append({
                'log_id': log.log_id,
                'content': log.content,
                'created_at': log.created_at,
                'keywords': keywords,
            })

        return JsonResponse({'logs': result_logs}, status=200)

    except Exception as e:
        return JsonResponse({'error': '유효하지 않은 요청입니다'}, status=400)