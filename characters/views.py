from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from logs.models import PlusLog
from cycle.models import Cycle
from .models import CharacterState

@require_http_methods(["GET"])
def get_character_room(request):
    user = request.user

    try:
        char_state = CharacterState.objects.filter(user=user).first()
        if not char_state:
            return JsonResponse({"error": "캐릭터 정보가 없습니다."}, status=404)

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

        return JsonResponse({
            "total_score": char_state.total_score,
            "current_stage": stage_name,
            "gauge": {
                "current": current_gauge,
                "max": max_gauge
            },
            "assets": assets_list
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": "캐릭터 방 조회 중 오류가 발생했습니다."}, status=500)