from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Cycle
from rest_framework.response import Response
from .serializers import FormerCycleAnalysisSerializer



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

        response_serializer = FormerCycleAnalysisSerializer(target_cycle)
        return Response(response_serializer.data, status=status.HTTP_200_OK)