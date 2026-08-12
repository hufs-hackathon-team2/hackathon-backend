from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    CharacterSelectSerializer,
    LoginSerializer,
    NotificationSettingsSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RefreshSerializer,
    SignupSerializer,
    WithdrawalSerializer,
)
from .services import (
    complete_onboarding,
    confirm_password_reset,
    issue_tokens,
    request_password_reset,
    signup,
)


def _validate_or_401(serializer):
    # DRF는 첫 번째 authentication_class가 WWW-Authenticate 헤더를 안 주면
    # AuthenticationFailed를 403으로 바꿔버려서, 401을 보장하려고 직접 처리한다.
    try:
        serializer.is_valid(raise_exception=True)
        return None
    except AuthenticationFailed as exc:
        return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)


class SignupView(APIView):
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, access, refresh = signup(**serializer.validated_data)
        return Response(
            {
                "user_id": user.user_id,
                "email": user.email,
                "nickname": user.nickname,
                "access": access,
                "refresh": refresh,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        error_response = _validate_or_401(serializer)
        if error_response:
            return error_response
        user = serializer.validated_data["user"]
        access, refresh = issue_tokens(user)
        return Response(
            {
                "user_id": user.user_id,
                "email": user.email,
                "onboarding_completed": user.onboarding_completed,
                "access": access,
                "refresh": refresh,
            },
            status=status.HTTP_200_OK,
        )


class RefreshView(APIView):
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        error_response = _validate_or_401(serializer)
        if error_response:
            return error_response
        user = serializer.validated_data["user"]
        jwt_token = serializer.validated_data["jwt_token"]
        return Response(
            {
                "access": str(jwt_token.access_token),
                "onboarding_completed": user.onboarding_completed,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        error_response = _validate_or_401(serializer)
        if error_response:
            return error_response
        db_token = serializer.validated_data["db_token"]
        db_token.revoked_at = timezone.now()
        db_token.save(update_fields=["revoked_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CharacterSelectView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = CharacterSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.character_id = serializer.validated_data["character_id"]
        request.user.save(update_fields=["character_id"])
        return Response(
            {"character_id": request.user.character_id}, status=status.HTTP_200_OK
        )


class OnboardingCompleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = complete_onboarding(request.user)
        return Response(
            {"onboarding_completed": user.onboarding_completed}, status=status.HTTP_200_OK
        )


class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(
            {"nickname": request.user.nickname, "email": request.user.email},
            status=status.HTTP_200_OK,
        )


class NotificationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = NotificationSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.notification_enabled = serializer.validated_data["enabled"]
        request.user.save(update_fields=["notification_enabled"])
        return Response(
            {"notification_enabled": request.user.notification_enabled},
            status=status.HTTP_200_OK,
        )


class WithdrawalView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        serializer = WithdrawalSerializer(data=request.data, context={"user": request.user})
        error_response = _validate_or_401(serializer)
        if error_response:
            return error_response
        request.user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_password_reset(serializer.validated_data["email"])
        return Response(status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirm_password_reset(
            serializer.validated_data["db_token"], serializer.validated_data["new_password"]
        )
        return Response(status=status.HTTP_200_OK)
