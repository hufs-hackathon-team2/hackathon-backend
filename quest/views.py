from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.generics import status, Response
from .serializers import QuestCreateSerializer, QuestResponseSerializer
from .models import Quest
from datetime import date
from cycle.services import close_and_start_new_cycle

class StartQuestAPIView(APIView):

    def post(self, request):
        create_serializer = QuestCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)  # 실패 시 자동으로 400 응답

        quest = Quest.objects.create(
            quest_content = create_serializer.validated_data['quest_content'],
            state='ACTIVE',
            started_at=date.today(),
            cycle=request.user.current_cycle,
        )

        close_and_start_new_cycle(request.user, date.today(), linked_record=quest)

        response_serializer = QuestResponseSerializer(quest)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
