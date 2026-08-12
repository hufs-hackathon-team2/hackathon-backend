from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, SignupSerializer
from .services import issue_tokens, signup


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
        # DRF는 첫 번째 authentication_class가 WWW-Authenticate 헤더를 안 주면
        # AuthenticationFailed를 403으로 바꿔버려서, 401을 보장하려고 직접 처리한다.
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as exc:
            return Response({"detail": str(exc.detail)}, status=status.HTTP_401_UNAUTHORIZED)
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
