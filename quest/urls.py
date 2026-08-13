from django.urls import path
from . import views

urlpatterns = [
    path('quests/', views.StartQuestAPIView.as_view(), name='start_quest'),
    path('quests/<int:quest_id>/check/', views.CheckQuestAPIView.as_view(), name='check_quest'),
    path('quests/<int:quest_id>/abandon/', views.AbandonQuestSerializer.as_view(), name='abandon_quest'),
    path('quests/active/', views.ActiveQuestsAPIView.as_view(), name='active_quests')
]