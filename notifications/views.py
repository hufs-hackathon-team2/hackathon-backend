from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PushPermissionSerializer


class PushPermissionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PushPermissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.push_permission_granted = serializer.validated_data["granted"]
        request.user.save(update_fields=["push_permission_granted"])
        return Response(
            {"push_permission_granted": request.user.push_permission_granted},
            status=status.HTTP_200_OK,
        )
