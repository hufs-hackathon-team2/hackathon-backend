from rest_framework import serializers


class CharacterGaugeSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    max = serializers.IntegerField()


class CharacterRoomResponseSerializer(serializers.Serializer):
    char_type = serializers.CharField()
    total_score = serializers.IntegerField()
    current_stage = serializers.CharField()
    gauge = CharacterGaugeSerializer()
    assets = serializers.ListField(
        child=serializers.CharField()
    )