import logging

from django.db.models import Sum
from django.utils import timezone
from datetime import date
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

        new_cycle = close_and_start_new_cycle(request.user, date.today(), linked_record=log_entry)

        is_new_cycle_started = bool(new_cycle)

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
                        temperature = 0.0,
                        timeout=10
        )

        llm_result = response.choices[0].message.content.strip()

        if llm_result == 'DANGER':
            log_entry.state = 'FAILED'
            log_entry.processed_at = timezone.now()
            log_entry.save()
            return Response({'error': '위험 키워드가 포함되어 로그 분석이 실패했습니다.'}, status=403)

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
        cycle_entry = request.user.current_cycle

        if not cycle_entry:
            return Response({'error': '현재 사이클이 없습니다. 온보딩을 완료해주세요.'}, status=400)

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