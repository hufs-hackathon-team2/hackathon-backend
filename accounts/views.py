from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, RefreshSerializer, SignupSerializer
from .services import issue_tokens, signup


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
