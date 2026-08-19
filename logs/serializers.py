from rest_framework import serializers


# LG-02. 로그 작성 요청
class LogCreateSerializer(serializers.Serializer):
    cycle_id = serializers.IntegerField()
    content = serializers.CharField(max_length=200)

# LG-02. 로그 작성 응답
class LogCreateResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    log_id = serializers.IntegerField()
    asset = serializers.CharField()
    new_cycle_started = serializers.BooleanField()

# LG-03. 로그 하나의 응답 구조
class LogItemSerializer(serializers.Serializer):
    log_id = serializers.IntegerField()
    content = serializers.CharField()
    created_at = serializers.DateTimeField()
    asset = serializers.CharField(allow_null=True)

# LG-03. 로그 목록 응답
class LogListResponseSerializer(serializers.Serializer):
    logs = LogItemSerializer(many=True)

# LG-04. 로그 삭제 응답
class LogDeleteResponseSerializer(serializers.Serializer):
    message = serializers.CharField()