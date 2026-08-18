from django.urls import path
from . import views

urlpatterns = [
    path('quests/', views.QuestCreateView.as_view(), name='start_quest'),
    path('quests/<int:quest_id>/check/', views.QuestCheckUpdateView.as_view(), name='check_quest'),
    path('quests/<int:quest_id>/abandon/', views.QuestAbandonUpdateView.as_view(), name='abandon_quest'),
    path('quests/<int:quest_id>/check/', views.QuestSuccessDetailView.as_view(), name='quest_success'),
    path('quests/active/', views.QuestActiveListView.as_view(), name='active_quests'),
    path('quests/recommendations/', views.QuestRecommendationListView.as_view(), name='AI_recommended_quests'),
    path('cycles/<int:cycle_id>/quests/', views.QuestAllListView.as_view(), name='all_quests_of_cycle'),
]