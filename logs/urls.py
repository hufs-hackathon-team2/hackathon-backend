from django.urls import path
from . import views

urlpatterns = [
    # LG-01, 02, 03: 생성(POST), 목록 조회(GET)
    path('', views.log_dispatcher, name='log_dispatcher'),

    # LG-04: 플러스 로그 삭제 (DELETE)
    path('<int:log_id>/', views.delete_log, name='delete_log'),
]