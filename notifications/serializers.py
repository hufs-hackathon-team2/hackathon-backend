from rest_framework import serializers


class PushPermissionSerializer(serializers.Serializer):
    granted = serializers.BooleanField()
