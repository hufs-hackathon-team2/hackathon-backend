from django.urls import path

from .views import (
    CharacterSelectView,
    LoginView,
    LogoutView,
    NotificationSettingsView,
    OnboardingCompleteView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RefreshView,
    SettingsView,
    SignupView,
    WithdrawalView,
)

# NOTE: 이 앱은 /auth/*, /users/*, /settings/* 등 여러 프리픽스의 엔드포인트를 함께
# 담당해서 각 path에 전체 경로를 직접 명시한다.
urlpatterns = [
    path("auth/signup/", SignupView.as_view(), name="signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path(
        "auth/password-reset/", PasswordResetRequestView.as_view(), name="password-reset"
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("users/me/character/", CharacterSelectView.as_view(), name="character-select"),
    path(
        "users/me/onboarding-complete/",
        OnboardingCompleteView.as_view(),
        name="onboarding-complete",
    ),
    path("settings/", SettingsView.as_view(), name="settings"),
    path(
        "settings/notifications/",
        NotificationSettingsView.as_view(),
        name="notification-settings",
    ),
    path("users/me/", WithdrawalView.as_view(), name="withdrawal"),
]
