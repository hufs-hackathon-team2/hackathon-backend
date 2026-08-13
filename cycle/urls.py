from django.urls import path
from . import views

urlpatterns = [
    path('cycle/analysis/<int:cycle_count>', views.GetCycleAnalysis.as_view(), name='former_cycle_analysis'),
]