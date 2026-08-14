from django.urls import path
from . import views

urlpatterns = [
    path('weekly-card/', views.WeeklyCardAPIView.as_view(), name='weekly_card'),
]