from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Cycle
from accounts.models import User
from rest_framework.response import Response
from .serializers import CycleAnalysisSerializer, CycleHistorySerializer
from weekly_card.services import AIAnalysisError
from .services import generate_cycle_analysis



####### 이전 싸이클 분석 조회 #######

class CycleAnalysisDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_count):
        target_cycle = get_object_or_404(Cycle, user=request.user, count=cycle_count)
        target_cycle_analysis = target_cycle.analysis

        if not target_cycle_analysis:
            return Response(
                {"error": "분석 결과가 없습니다."},
                status=status.HTTP_404_NOT_FOUND
            )

        response_serializer = CycleAnalysisSerializer(target_cycle)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

####### 현재 싸이클 분석 조회 #######
class CurrentCycleAnalysisAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        target_cycle = request.user.current_cycle

        if not target_cycle:
            return Response(
                {"error": "현재 사이클이 없습니다. 온보딩을 완료해주세요."},
                status=status.HTTP_404_NOT_FOUND
            )

        if target_cycle.analysis_request_count >= 3:
            return Response(
                {"error": "현재 사이클 분석 요청 횟수가 3회를 초과하였습니다."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        try:
            result = generate_cycle_analysis(target_cycle)
        except AIAnalysisError:
            return Response(
                {"error": "AI 서비스를 실행할 수 없습니다."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        target_cycle.analysis = result
        target_cycle.analysis_request_count += 1
        target_cycle.save(update_fields=['analysis', 'analysis_request_count'])

        response_serializer = CycleAnalysisSerializer(target_cycle)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def get(self, request):

        target_cycle = request.user.current_cycle

        if not target_cycle:
            return Response(
                {"error": "현재 사이클이 없습니다. 온보딩을 완료해주세요."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        response_serializer = CycleAnalysisSerializer(target_cycle)
        return Response(response_serializer.data, status=status.HTTP_200_OK)

class CycleHistoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        cycles = Cycle.objects.filter(
            user=request.user,
            closed_at__isnull=False, #이전 사이클만 가져옴
        )

        response_serializer = CycleHistorySerializer(cycles, many=True)

        response = {
            "cycles": [response_serializer.data]
        }

        return Response(response, status=status.HTTP_200_OK)
