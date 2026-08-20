import logging

from django.db.models import Sum
from django.utils import timezone
from decouple import config
from openai import OpenAI

from .constants import ASSET_LIST
from .models import PlusLog, Asset
from .serializers import (
    LogCreateSerializer,
    LogCreateResponseSerializer,
    LogListResponseSerializer,
    LogDeleteResponseSerializer,
)

from cycle.models import Cycle
from cycle.services import close_and_start_new_cycle
from characters.models import CharacterState, CharacterGrowthEvent

from django.core.paginator import Paginator

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

#LG-02. 키워드 추출 및 에셋 매핑
client = OpenAI(api_key=config('OPEN_AI_API_KEY'))
logger = logging.getLogger(__name__)

def create_and_analyze_log(request):
    data = request.data

    content = data.get('content')

    if (
        not isinstance(content, str)
        or not content.strip()
    ):
            return Response(
                {'error': 'content 필드가 필요합니다.'},
                status=400
            )

    if len(content) > 200:
        return Response(
            {'error': 'content는 200자 이내로 입력해주세요.'},
            status=400
        )

    cycle_entry = request.user.current_cycle

    if cycle_entry is None:
        return Response({
            'error': '현재 사이클이 없습니다.'
        }, status=403)

    if cycle_entry.state not in [Cycle.State.ACTIVE, Cycle.State.RESTING]:
        return Response({
            'error': '현재 진행 중인 사이클에만 로그를 작성할 수 있습니다.'
        }, status=403)

    today = timezone.localtime().date()
    has_log_today = PlusLog.objects.filter(
        user=request.user,
        created_at__date=today,
        deleted_at__isnull=True
    ).exists()
    
    try:
        log_entry = PlusLog.objects.create(
            user=request.user,
            cycle=cycle_entry,
            content=content,
            state='PENDING'
        )

        new_cycle = close_and_start_new_cycle(request.user, timezone.localdate(), linked_record=log_entry)

        is_new_cycle_started = bool(new_cycle)

        asset_options_str = ", ".join([f"{a['action']}({a['asset_name']})" for a in ASSET_LIST])

        system_prompt = f"""
        너는 유저 로그를 분석해서 가장 알맞은 에셋을 추출하는 시스템이야.
        [선택 가능한 에셋 리스트: 행동/의미(영어단어)]
        {asset_options_str}

        [위험(DANGER) 판단 기준]
        이 앱은 신체적/정신적 건강을 즐겁게 지속하도록 돕는 '헬시 플레저(Healthy Pleasure)' 서비스야.
        '위험'은 신체 건강 또는 정신 건강에 실질적으로 해가 되는 왜곡된 생각이나 행동으로 한정해.
        아래처럼 명확한 경우에만 DANGER로 판단해:
        - 극단적인 단식/절식을 긍정적으로 여기는 표현 (예: "오늘 하루 종일 굶었음", "이틀째 아무것도 안 먹음")
        - 자해, 자살 관련 언급
        - 폭식 후 의도적 구토 등 섭식장애성 행동
        - 무리한 다이어트약/보충제 남용, 스스로를 해치는 수준의 과도한 운동
        - 명확한 자기비하·자기혐오 표현
        아래는 DANGER가 아니야:
        - 단순히 뜻을 모르겠거나 애매한 표현
        - 일반적인 다이어트/식단 조절 (예: "저녁은 가볍게 물만 마심", "간헐적 단식 중")
        - 단순 피로/스트레스 호소처럼 흔한 감정 표현

        [필수 규칙]
        1. 위 기준에 명확히 해당할 때만 DANGER로 판단해.
        2. 구체적인 행동이 있다면 반드시 행동을 우선으로 선택 (감정보다 행동 우선)
        3. 비슷한 에셋이 여러 개라면 더 구체적인 쪽을 선택 (예. 운동 vs 등산 -> 등산 선택)
        4. 로그 내용과 일치하는 에셋이 없거나, 의미를 알 수 없는 무작위 문자/오타/한글 자모(예. "ㅇㅁㄻㄹㄷ")처럼 실제 활동을 특정할 수 없는 내용이면 위험이 아닌 이상 무조건 'sprout'를 반환해.
        5. 응답은 반드시 한 줄로만, 아래 형식 중 하나로만 작성해. 다른 설명이나 마크다운, 따옴표는 절대 붙이지 마.
           - 위험이 아니면: 에셋명만 그대로 (예: run)
           - 위험이면: "DANGER: 판단 이유 한 문장" (예: DANGER: 하루 종일 굶는 건 건강에 해로울 수 있어요)
        """

        user_prompt = f"로그 내용: \"{content}\"\n\n위 로그에 가장 적합한 에셋 1개 또는 DANGER 판단 결과를 출력하세요."

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        max_tokens= 80,
                        temperature = 0.0,
                        timeout=10
        )

        llm_result = response.choices[0].message.content.strip()

        if llm_result.startswith('DANGER'):
            reason = llm_result.split(':', 1)[1].strip() if ':' in llm_result else '건강에 위험할 수 있는 내용이 포함되어 있어요.'
            log_entry.delete()
            return Response(
                {'error': '위험 키워드가 포함되어 로그 분석이 실패했습니다.', 'reason': reason},
                status=403,
            )

        valid_asset_names = [a['asset_name'] for a in ASSET_LIST]
        final_asset_name = llm_result if llm_result in valid_asset_names else 'sprout'

        try:
            asset = Asset.objects.get(asset_name=final_asset_name, is_active=True)
        except Asset.DoesNotExist:
            asset = Asset.objects.get(asset_name='sprout', is_active=True)

        log_entry.asset = asset
        log_entry.state = 'DONE'
        log_entry.processed_at = timezone.now()
        log_entry.save()

        if not has_log_today:
            char_state, created = CharacterState.objects.get_or_create(user=request.user)
            char_state.total_score += 1
            char_state.save()

            CharacterGrowthEvent.objects.create(
                char_state=char_state,
                source_type=CharacterGrowthEvent.SourceType.LOG,
                score=1,
                log=log_entry
            )

        return Response({
            'message': '로그 분석 성공',
            'log_id': log_entry.log_id,
            'asset': final_asset_name,
            'new_cycle_started': is_new_cycle_started,
        }, status=200)

    except Exception:
        logger.exception("플러스 로그 처리 실패 (user=%s)", request.user.user_id)
        if 'log_entry' in locals():
            log_entry.state = 'FAILED'
            log_entry.processed_at = timezone.now()
            log_entry.save()
        return Response(
            {'error': '로그 처리 중 오류 발생'},
            status=500
            )


# LG-03. 기록 목록 조회
def get_log_list(request):
    try:
        page_number = request.query_params.get('page', 1)

        logs_query = PlusLog.objects.filter(
            user=request.user,
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

        return Response({'logs': result_logs}, status=200)

    except Exception as e:
        return Response({'error': '유효하지 않은 요청입니다'}, status=400)

@extend_schema(
    summary="플러스 로그 작성",
    request=LogCreateSerializer,
    responses={
        200: LogCreateResponseSerializer,
        400: None,
        403: None,
        500: None,
    },
    methods=['POST'],
)
@extend_schema(
    summary="플러스 로그 목록 조회",
    parameters=[
        OpenApiParameter(name="page", description="페이지 번호", required=False, type=OpenApiTypes.INT),
    ],
    responses={
        200: LogListResponseSerializer,
        400: None,
    },
    methods=['GET'],
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def log_dispatcher(request):
    if request.method == 'GET':
        return get_log_list(request)
    elif request.method == 'POST':
        return create_and_analyze_log(request)

# LG-04. 기록 삭제
@extend_schema(
    responses={
        200: LogDeleteResponseSerializer,
        404: None,
        500: None,
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_log(request, log_id):
    try:
        log_entry = PlusLog.objects.get(
            log_id=log_id, 
            user=request.user,
            deleted_at__isnull=True
        )

        log_entry.deleted_at = timezone.now()
        log_entry.save()

        # 이 로그로 획득했던 캐릭터 성장 게이지가 있으면 회수한다.
        reclaimed_score = CharacterGrowthEvent.objects.filter(
            source_type=CharacterGrowthEvent.SourceType.LOG,
            log=log_entry,
        ).aggregate(total=Sum('score'))['total'] or 0

        if reclaimed_score:
            char_state = log_entry.user.character_state
            char_state.total_score = max(0, char_state.total_score - reclaimed_score)
            char_state.save(update_fields=['total_score'])

        return Response({'message': '로그 삭제 성공'}, status=200)

    except PlusLog.DoesNotExist:
        return Response({'error': '존재하지 않는 로그입니다.'}, status=404)
    except Exception as e:
        return Response({'error': '로그 삭제 중 오류 발생'}, status=500)