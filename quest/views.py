from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import QuestCreateSerializer, QuestResponseSerializer, CheckQuestSerializer, AbandonQuestSerializer
from .models import Quest
from datetime import date
from cycle.services import close_and_start_new_cycle
from quest.services import check_for_quest, InvalidTransition, QuestAlreadyChecked, abandon_quest
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

class StartQuestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        create_serializer = QuestCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)  # 실패 시 자동으로 400 응답

        #동일 퀘스트가 진행중인지 판정
        quest_content = create_serializer.validated_data['quest_content']
        active_quests = Quest.objects.filter(user=request.user, state='ACTIVE')
        if quest_content in [q.quest_content for q in active_quests]:
            return Response(status=status.HTTP_409_CONFLICT)

        if request.user.current_cycle is None:
            return Response(
                {"detail": "진행 중인 사이클이 없습니다. 온보딩을 먼저 완료해주세요."},
                status=status.HTTP_400_BAD_REQUEST
            )

        quest = Quest.objects.create(
            user=request.user,
            quest_content = create_serializer.validated_data['quest_content'],
            state='ACTIVE',
            started_at=date.today(),
            cycle=request.user.current_cycle,
        )
        
        close_and_start_new_cycle(request.user, date.today(), linked_record=quest)

        response_serializer = QuestResponseSerializer(quest)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

class CheckQuestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):

        quest = get_object_or_404(Quest, id=quest_id, cycle__user_id_placeholder=request.user)
        try:
            result = check_for_quest(quest, date.today())
            response_serializer = CheckQuestSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except InvalidTransition as e:
            return Response({"error": "INVALID_STATE_TRANSITION", "message": str(e)}, status=status.HTTP_409_CONFLICT)
        except QuestAlreadyChecked as e:
            return Response({"error": "ALREADY_CHECKED_TODAY", "message": str(e)}, status=status.HTTP_409_CONFLICT)


class AbandonQuestAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):
        quest = get_object_or_404(Quest, id=quest_id, cycle__user_id_placeholder=request.user)
        try:
            result = abandon_quest(quest)
            response_serializer = AbandonQuestSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except InvalidTransition as e:
            return Response({"error": "INVALID_STATE_TRANSITION", "message": str(e)}, status=status.HTTP_409_CONFLICT)