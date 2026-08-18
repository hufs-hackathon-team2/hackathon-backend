from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from logs.models import PlusLog
from cycle.models import Cycle
from .models import CharacterState
from .serializers import CharacterRoomResponseSerializer

@extend_schema(
    summary="캐릭터 방 조회",
    description="현재 사용자의 캐릭터 상태와 성장 게이지, 현재 사이클의 최근 에셋 목록을 조회합니다.",
    responses={
        200: CharacterRoomResponseSerializer,
        404: {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string"
                }
            }
        },
        500: {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string"
                }
            }
        }
    },
    tags=["Characters"],
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_character_room(request):
    user = request.user

    try:
        char_state = CharacterState.objects.filter(user=user).first()
        if not char_state:
            return Response({"error": "캐릭터 정보가 없습니다."}, status=404)

        stage_name, current_gauge, max_gauge = char_state.get_stage_and_gauge()

        current_cycle = Cycle.objects.filter(user=user, state='ACTIVE').first()

        assets_list = []
        if current_cycle:
            recent_logs = PlusLog.objects.filter(
                cycle=current_cycle,
                state='DONE',
                deleted_at__isnull=True,
            ).select_related('asset').order_by('-created_at')[:14]

            assets_list = [log.asset.asset_name for log in recent_logs if log.asset]

        return Response({
            "char_type": char_state.char_type,
            "total_score": char_state.total_score,
            "current_stage": stage_name,
            "gauge": {
                "current": current_gauge,
                "max": max_gauge
            },
            "assets": assets_list
        }, status=200)

    except Exception as e:
        return Response({"error": "캐릭터 방 조회 중 오류가 발생했습니다."}, status=500)