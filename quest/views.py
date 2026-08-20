from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response
from .serializers import QuestCreateSerializer, QuestResponseSerializer, CheckQuestSerializer, AbandonQuestSerializer, CurrentQuestSerializer, AIRecommendationResponseSerializer, AllQuestsOfCycleResponseSerializer, QuestSuccessDetailSerializer
from .models import Quest
from accounts.models import User
from cycle.models import Cycle
from weekly_card.models import RecommendedQuest, WeeklyAnalysis
from django.utils import timezone
from cycle.services import close_and_start_new_cycle
from quest.services import (
    check_for_quest,
    InvalidTransition,
    QuestAlreadyChecked,
    abandon_quest,
    sync_active_quest_state,
)
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

####### 퀘스트 시작 #######
class QuestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QuestCreateSerializer, tags=["Quest"])
    def post(self, request):
        create_serializer = QuestCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)  # 실패 시 자동으로 400 응답

        quest_content = create_serializer.validated_data['quest_content']

        if request.user.current_cycle is None:
            return Response(
                {"detail": "진행 중인 사이클이 없습니다. 온보딩을 먼저 완료해주세요."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 퀘스트는 한 번에 하나만 ACTIVE로 진행할 수 있다.
        today = timezone.localdate()
        sync_active_quest_state(request.user, today)
        has_active_quest = Quest.objects.filter(
            cycle__user=request.user,
            state=Quest.State.ACTIVE,
        ).exists()
        if has_active_quest:
            return Response(
                {"detail": "이미 진행중인 퀘스트가 있습니다. 완료하거나 포기한 뒤 새로 시작해주세요."},
                status=status.HTTP_409_CONFLICT
            )

        # 포기 직후 바로 재시작해서 체크하는 방식으로 게이지를 무한정 불리는 걸 막는다.
        abandoned_today = Quest.objects.filter(
            cycle__user=request.user,
            state=Quest.State.ABANDONED,
            abandoned_at=today,
        ).exists()
        if abandoned_today:
            return Response(
                {"detail": "퀘스트를 포기한 당일에는 새 퀘스트를 시작할 수 없습니다. 내일 다시 시도해주세요."},
                status=status.HTTP_409_CONFLICT
            )


        quest = Quest.objects.create(
            quest_content = create_serializer.validated_data['quest_content'],
            state='ACTIVE',
            started_at=today,
            cycle=request.user.current_cycle,
        )

        new_cycle = close_and_start_new_cycle(request.user, today, linked_record=quest)

        is_new_cycle_started = new_cycle is not None

        response_serializer = QuestResponseSerializer(
            quest,
            context={'new_cycle_started': is_new_cycle_started})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

####### 퀘스트 수행 체크 #######
class QuestCheckUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):

        quest = get_object_or_404(Quest, id=quest_id, cycle__user=request.user)
        try:
            result = check_for_quest(quest, timezone.localdate())
            response_serializer = CheckQuestSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except InvalidTransition as e:
            return Response({"error": "INVALID_STATE_TRANSITION", "message": str(e)}, 
                            status=status.HTTP_409_CONFLICT)
        except QuestAlreadyChecked as e:
            return Response({"error": "ALREADY_CHECKED_TODAY", "message": str(e)}, 
                            status=status.HTTP_409_CONFLICT)

####### 퀘스트 포기 #######
class QuestAbandonUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, quest_id):
        quest = get_object_or_404(Quest, id=quest_id, cycle__user=request.user)
        try:
            result = abandon_quest(quest, timezone.localdate())
            response_serializer = AbandonQuestSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except InvalidTransition as e:
            return Response({"error": "INVALID_STATE_TRANSITION", "message": str(e)}, 
                            status=status.HTTP_409_CONFLICT)

####### 수행중인 퀘스트 목록 조회 #######
class QuestActiveListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sync_active_quest_state(request.user, timezone.localdate())
        quests = Quest.objects.filter(
            cycle__user=request.user,
            state=Quest.State.ACTIVE
        )

        serializer = CurrentQuestSerializer(quests, many=True)
        return Response(
            {
                "has_active_quest": quests.exists(),
                "active_quests": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

####### AI 추천 퀘스트 목록 조회 #######
class QuestRecommendationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # 직전 주에 한정하지 않고, 추천 퀘스트가 실제로 딸린 가장 최근 주간 분석을 찾는다.
        # 휴식기를 오래 가진 뒤 재개해도(직전 주엔 분석이 없어도) 마지막으로 받은 추천을 볼 수 있어야 한다.
        latest_analysis = WeeklyAnalysis.objects.filter(
            user=user,
            recommendations__isnull=False,
        ).distinct().order_by('-week_start').first()

        if latest_analysis is None:
            data = {
                'has_recommendations': False,
                'week_start': None,
                'recommended_quests': RecommendedQuest.objects.none(),
                'plus_log_count': 0,
                'required_log_count': 2,
            }
        else:
            recommended_quests = latest_analysis.recommendations.all()
            data = {
                'has_recommendations': recommended_quests.exists(),
                'week_start': latest_analysis.week_start,
                'recommended_quests': recommended_quests,
                'plus_log_count': latest_analysis.plus_log_count,
                'required_log_count': 2,
            }
        response_serializer = AIRecommendationResponseSerializer(data)

        return Response(response_serializer.data, status=status.HTTP_200_OK)

####### 퀘스트 성공 화면 조회 #######
class QuestSuccessDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, quest_id):
        quest = get_object_or_404(
            Quest.objects.select_related('cycle__user__character_state'), 
            id=quest_id,
            cycle__user=request.user 
        )
        response_serializer = QuestSuccessDetailSerializer(quest)

        return Response(response_serializer.data, status=status.HTTP_200_OK)

        

####### 사이클의 모든 퀘스트 조회 #######
class QuestAllListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_id):
        target_cycle = get_object_or_404(Cycle, id=cycle_id)

        if target_cycle.user != request.user:
            return Response({"error": "요청한 사용자의 사이클이 아닙니다."}, 
                            status=status.HTTP_403_FORBIDDEN)

        all_quests_of_cycle = Quest.objects.filter(
            cycle = target_cycle,
        )

        data = {
            "cycle_id": target_cycle.id,
            "quests": all_quests_of_cycle
        }

        response_serializer = AllQuestsOfCycleResponseSerializer(data)

        return Response(response_serializer.data, status=status.HTTP_200_OK)