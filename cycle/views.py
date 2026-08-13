from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Cycle, User
from rest_framework.response import Response
from .serializers import CycleAnalysisSerializer



####### 이전 싸이클 분석 조회 #######

class GetCycleAnalysis(APIView):
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
class GetCurrentCycleAnalysis(APIView):
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
            #TODO: AI호출해서 분석 받아오는 함수 구현 (services.py)
            result = request_current_cycle_analysis(target_cycle)
        except: #TODO: AI호출 함수에서 에러 커스텀해서 여기 넣기
            return Response(
                {"error": "AI 서비스를 실행할 수 없습니다."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        target_cycle.analysis = result
        target_cycle.analysis_request_count += 1
        target_cycle.save(update_fields=['analysis_request_count'])

        response_serializer = CycleAnalysisSerializer(target_cycle)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    