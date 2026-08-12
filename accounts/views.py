from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import SignupSerializer
from .services import signup


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
