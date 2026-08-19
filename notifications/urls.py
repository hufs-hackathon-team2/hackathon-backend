from django.urls import re_path

from .views import PushPermissionView

# accounts/urls.py와 동일한 이유로 끝 슬래시를 선택적으로 허용한다.
urlpatterns = [
    re_path(r"^notifications/permission/?$", PushPermissionView.as_view(), name="push-permission"),
]
