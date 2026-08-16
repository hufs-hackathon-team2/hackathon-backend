import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from decouple import config
from openai import OpenAI

from .constants import ASSET_LIST
from .models import PlusLog, Asset
from cycle.models import Cycle

from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404

#LG-02. 키워드 추출 및 에셋 매핑
client = OpenAI(api_key=config('OPENAI_API_KEY'))

@require_POST
def create_and_analyze_log(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': '잘못된 JSON 형식입니다.'}, status=400)
    
    cycle_id = data.get('cycle_id')
    content = data.get('content')

    if (
        cycle_id is None
        or not isinstance(content, str)
        or not content.strip()
    ):
            return JsonResponse(
                {'error': 'cycle_id, content 필드가 모두 필요합니다.'}, 
                status=400
            )

    if len(content) > 200:
        return JsonResponse(
            {'error': 'content는 200자 이내로 입력해주세요.'},
            status=400
        )

    cycle_entry = get_object_or_404(Cycle, pk=cycle_id, user=request.user)
    
    try:
        log_entry = PlusLog.objects.create(
            user=request.user,
            cycle=cycle_entry,
            content=content,
            state='PENDING'
        )

        asset_options_str = ", ".join([f"{a['action']}({a['asset_name']})" for a in ASSET_LIST])

        system_prompt = f"""
        너는 유저 로그를 분석해서 가장 알맞은 에셋을 추출하는 시스템이야.
        [선택 가능한 에셋 리스트: 행동/의미(영어단어)]
        {asset_options_str}
        [필수 규칙]
        1. 사용자의 로그에 건강을 해칠 수 있는 위험 키워드(예. 극단적 다이어트, 자해 등)가 있다면 절대로 에셋을 추출하지 말고 오직 'DANGER'라고만 응답해.
        2. 구체적인 행동이 있다면 반드시 행동을 우선으로 선택 (감정보다 행동 우선)
        3. 비슷한 에셋이 여러 개라면 더 구체적인 쪽을 선택 (예. 운동 vs 등산 -> 등산 선택)
        4. 로그 내용과 일치하는 에셋이 목록에 전혀 없다면 무조건 'sparkles'라는 에셋을 반환.
        5. 어떠한 설명도 덧붙이지 말고, 오직 '에셋명(예: run)' 또는 'DANGER'만 반환해.
        """

        user_prompt = f"로그 내용: \"{content}\"\n\n위 로그에 가장 적합한 에셋 1개를 출력하세요."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens= 20,
                        temperature = 0.0
        )

        llm_result = response.choices[0].message.content.strip()

        if llm_result == 'DANGER':
            log_entry.state = 'FAILED'
            log_entry.processed_at = timezone.now()
            log_entry.save()
            return JsonResponse({'error': '위험 키워드가 포함되어 로그 분석이 실패했습니다.'}, status=403)

        valid_asset_names = [a['asset_name'] for a in ASSET_LIST]
        final_asset_name = llm_result if llm_result in valid_asset_names else 'sparkles'

        try:
            asset = Asset.objects.get(asset_name=final_asset_name, is_active=True)
        except Asset.DoesNotExist:
            asset = Asset.objects.get(asset_name='sparkles', is_active=True)

        log_entry.asset = asset
        log_entry.state = 'DONE'
        log_entry.processed_at = timezone.now()
        log_entry.save()

        return JsonResponse({
            'message': '로그 분석 성공',
            'log_id': log_entry.log_id,
            'asset': final_asset_name
        }, status=200)

    except Exception as e:
        if 'log_entry' in locals():
            log_entry.state = 'FAILED'
            log_entry.processed_at = timezone.now()
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

        cycle_entry = get_object_or_404(Cycle, pk=cycle_id, user=request.user)

        logs_query = PlusLog.objects.filter(
            cycle=cycle_entry,
            deleted_at__isnull=True
        ).select_related('asset').order_by('-created_at')


        paginator = Paginator(logs_query, 10)
        page_obj = paginator.get_page(page_number)

        result_logs = []
        for log in page_obj:
            asset_name = log.asset.asset_name if log.asset else None
            
            result_logs.append({
                'log_id': log.log_id,
                'content': log.content,
                'created_at': log.created_at,
                'asset': asset_name,
            })

        return JsonResponse({'logs': result_logs}, status=200)

    except Exception as e:
        return JsonResponse({'error': '유효하지 않은 요청입니다'}, status=400)


# LG-04. 기록 삭제
@require_http_methods(["DELETE"])
def delete_log(request, log_id):
    try:
        log_entry = PlusLog.objects.get(
            log_id=log_id, 
            user=request.user,
            deleted_at__isnull=True
        )

        log_entry.deleted_at = timezone.now()
        log_entry.save()

        return JsonResponse({'message': '로그 삭제 성공'}, status=200)

    except PlusLog.DoesNotExist:
        return JsonResponse({'error': '존재하지 않는 로그입니다.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': '로그 삭제 중 오류 발생'}, status=500)


@csrf_exempt
def log_dispatcher(request):
    if request.method == 'GET':
        return get_log_list(request)
    elif request.method == 'POST':
        return create_and_analyze_log(request)
    else:
        return JsonResponse({'error': '허용되지 않은 메서드입니다.'}, status=405)