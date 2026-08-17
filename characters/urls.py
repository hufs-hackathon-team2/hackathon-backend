from django.urls import path
from . import views

urlpatterns = [
    path('me/room', views.get_character_room, name='character_room'),
]