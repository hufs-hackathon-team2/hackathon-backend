from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import NextWeekQuestsSerializer, WeeklyCardSerializer
from datetime import timedelta
from django.utils import timezone
from .models import WeeklyAnalysis
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response


class WeeklyCardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday() + 7)
        target_weekly_analysis = WeeklyAnalysis.objects.filter(
            user=request.user,
            week_start=week_start).first()

        if target_weekly_analysis is None:
            return Response({"is_generated": False}, status=status.HTTP_200_OK)

        response_serializer = WeeklyCardSerializer(
            target_weekly_analysis,
            context={'is_generated': True})

        return Response(response_serializer.data, status=status.HTTP_200_OK)