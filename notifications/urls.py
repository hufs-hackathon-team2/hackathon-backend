from django.urls import path

from .views import PushPermissionView

urlpatterns = [
    path("notifications/permission/", PushPermissionView.as_view(), name="push-permission"),
]
