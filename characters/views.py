from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from logs.models import PlusLog
from cycle.models import Cycle
from .models import CharacterState, CharacterArchive
from .serializers import CharacterRoomResponseSerializer

from .serializers import (
    CharacterRoomResponseSerializer, 
    CharacterArchiveResponseSerializer,
    ArchiveListResponseSerializer
)

from django.utils import timezone
from rest_framework import status

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
            ).select_related('asset').order_by('-created_at')[:16]

            assets_list = [log.asset.asset_name for log in recent_logs if log.asset]

        is_completed = (stage_name == CharacterState.Stage.STAGE_4_FINAL.value)

        started_at_str = char_state.created_at.strftime('%Y-%m-%d') if char_state.created_at else None 

        completed_at_str = None
        days_together = None
        if is_completed and char_state.updated_at:
            completed_at_str = char_state.updated_at.strftime('%Y-%m-%d')
            days_together = (char_state.updated_at.date() - char_state.created_at.date()).days + 1

        return Response({
            "char_type": char_state.char_type,
            "total_score": char_state.total_score,
            "current_stage": stage_name,
            "gauge": {
                "current": current_gauge,
                "max": max_gauge
            },
            "assets": assets_list,
            "is_completed": is_completed,
            "character_name": user.character_name,
            "started_at": started_at_str,
            "completed_at": completed_at_str,
            "days_together": days_together,
        }, status=200)

    except Exception as e:
        return Response({"error": "캐릭터 방 조회 중 오류가 발생했습니다."}, status=500)


@extend_schema(
    summary="캐릭터 아카이브 처리",
    description="4단계 Final 캐릭터를 보관함으로 이동시킵니다.",
    responses={
        200: CharacterArchiveResponseSerializer,
        400: {"type": "object", "properties": {"detail": {"type": "string", "example": "아직 완성되지 않은 캐릭터입니다."}}},
        500: {"type": "object", "properties": {"error": {"type": "string"}}}
    },
    tags=["Characters"],
    methods=['POST']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_character(request):
    user = request.user

    try:
        char_state = CharacterState.objects.filter(user=user).first()
        if not char_state:
            return Response({"detail": "캐릭터 정보가 없습니다."}, status=status.HTTP_404_NOT_FOUND)

        stage_name, _, _ = char_state.get_stage_and_gauge()
        
        # 45칸 다 채웠는지 검증
        if stage_name != CharacterState.Stage.STAGE_4_FINAL.value:
            return Response(
                {"detail": "아직 완성되지 않은 캐릭터입니다."},
                status=status.HTTP_400_BAD_REQUEST
            )

        char_type_str = user.character_type.upper() if user.character_type else "cat"

        # 1. 아카이브 기록 생성
        archive_record = CharacterArchive.objects.create(
            user=user,
            char_type=char_type_str,
            character_name=user.character_name,
            started_at=char_state.created_at
        )

        # 2. 기존 상태 완전 초기화
        char_state.total_score = 0
        char_state.created_at = timezone.now()
        char_state.save()

        # 3. User 캐릭터 정보 초기화 (CheckConstraint 위반 방지)
        user.character_type = None
        user.character_name = ""
        user.save()

        return Response({"archived_id": archive_record.id}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": "캐릭터 보관 중 오류가 발생했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 아카이브에 보관된 캐릭터 목록 조회 (GET)
@extend_schema(
    summary="앨범(아카이브) 목록 조회",
    description="보관함에 저장된 완료 캐릭터 목록을 불러옵니다. 비어있으면 빈 배열을 반환합니다.",
    responses={
        200: ArchiveListResponseSerializer,
        500: {"type": "object", "properties": {"error": {"type": "string"}}}
    },
    tags=["Characters"],
    methods=['GET']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_archive_list(request):
    try:
        # -completed_at으로 가져오기
        archives = CharacterArchive.objects.filter(user=request.user)
        
        # 데이터를 직렬화 (빈 배열일 경우 알아서 [] 로 반환됩니다)
        serializer = ArchiveListResponseSerializer({"characters": archives})
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({"error": "앨범 목록 조회 중 오류가 발생했습니다."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)