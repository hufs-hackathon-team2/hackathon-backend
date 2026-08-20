from django.urls import path
from . import views

urlpatterns = [
    path('me/room/', views.get_character_room, name='character_room'),

    # 캐릭터 보관 처리 (POST)
    path('me/archive/', views.archive_character, name='archive_character'),
    
    # 캐릭터 앨범 목록 조회 (GET)
    path('archive/', views.get_archive_list, name='archive_list'),
]