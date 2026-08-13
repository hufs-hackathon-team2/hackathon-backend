from django.urls import path
from . import views

urlpatterns = [
    path('cycle/analysis/<int:cycle_count>', views.FormerCycleAnalysisSerializer.as_view(), name='former_cycle_analysis'),
]