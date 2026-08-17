from django.urls import re_path

from .views import (
    CharacterSelectView,
    InterestView,
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
# NOTE: 끝 슬래시(/) 유무를 프론트가 혼용해서 보내서, re_path로 둘 다 받는다
# (Django의 APPEND_SLASH 리다이렉트는 POST/PATCH/DELETE에서 body가 유실될 수 있어 믿지 않는다).
urlpatterns = [
    re_path(r"^auth/signup/?$", SignupView.as_view(), name="signup"),
    re_path(r"^auth/login/?$", LoginView.as_view(), name="login"),
    re_path(r"^auth/refresh/?$", RefreshView.as_view(), name="refresh"),
    re_path(r"^auth/logout/?$", LogoutView.as_view(), name="logout"),
    re_path(
        r"^auth/password-reset/?$", PasswordResetRequestView.as_view(), name="password-reset"
    ),
    re_path(
        r"^auth/password-reset/confirm/?$",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    re_path(r"^users/me/interest/?$", InterestView.as_view(), name="interest-select"),
    re_path(r"^users/me/character/?$", CharacterSelectView.as_view(), name="character-select"),
    re_path(
        r"^users/me/onboarding-complete/?$",
        OnboardingCompleteView.as_view(),
        name="onboarding-complete",
    ),
    re_path(r"^settings/?$", SettingsView.as_view(), name="settings"),
    re_path(
        r"^settings/notifications/?$",
        NotificationSettingsView.as_view(),
        name="notification-settings",
    ),
    re_path(r"^users/me/?$", WithdrawalView.as_view(), name="withdrawal"),
]
