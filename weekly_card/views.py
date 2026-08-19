from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import NextWeekQuestsSerializer, WeeklyCardSerializer
from datetime import date, timedelta
from .models import WeeklyAnalysis
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response


class WeeklyCardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        week_start = date.today() - timedelta(days=date.today().weekday() + 7)
        target_weekly_analysis = WeeklyAnalysis.objects.get(
            user=request.user,
            week_start=week_start)

        is_generated = target_weekly_analysis is not None

        response_serializer = WeeklyCardSerializer(
            target_weekly_analysis,
            context={'is_generated': is_generated})

        return Response(response_serializer.data, status=status.HTTP_200_OK)