from django.urls import path
from . import views

urlpatterns = [
    path('cycle/analysis/current/', views.CurrentCycleAnalysisAPIView.as_view(), name='current_cycle_analysis'),
    path('cycle/analysis/<int:cycle_count>/', views.CycleAnalysisDetailView.as_view(), name='former_cycle_analysis'),
    path('cycle/history/', views.CycleHistoryListView.as_view(), name='cycle_history')
]