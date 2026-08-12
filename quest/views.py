from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import QuestCreateSerializer, QuestResponseSerializer
from .models import Quest
from datetime import date
from cycle.services import close_and_start_new_cycle
from rest_framework.permissions import IsAuthenticated

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
