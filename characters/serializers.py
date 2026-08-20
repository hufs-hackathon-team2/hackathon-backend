from rest_framework import serializers
from .models import CharacterArchive


class CharacterGaugeSerializer(serializers.Serializer):
    current = serializers.IntegerField()
    max = serializers.IntegerField()


class CharacterRoomResponseSerializer(serializers.Serializer):
    is_completed = serializers.BooleanField(help_text="캐릭터 최종 성장 완료 여부")
    character_name = serializers.CharField(help_text="캐릭터 이름")
    started_at = serializers.DateField(allow_null=True, help_text="캐릭터 성장 시작일 (YYYY-MM-DD)")
    completed_at = serializers.DateField(allow_null=True, help_text="캐릭터 성장 완료일 (YYYY-MM-DD)")
    days_together = serializers.IntegerField(allow_null=True, help_text="함께한 일수 (완료된 경우에만 값이 채워짐)")

    char_type = serializers.CharField()
    total_score = serializers.IntegerField()
    current_stage = serializers.CharField()
    gauge = CharacterGaugeSerializer()
    assets = serializers.ListField(
        child=serializers.CharField()
    )


# POST /characters/me/archive/
class CharacterArchiveResponseSerializer(serializers.Serializer):
    archived_id = serializers.IntegerField(help_text="보관된 캐릭터의 고유 ID")


# GET /characters/archive/
class ArchivedCharacterItemSerializer(serializers.ModelSerializer):
    character_id = serializers.IntegerField(
        source='id',
        read_only=True
    )

    started_at = serializers.DateTimeField(
        format="%Y-%m-%d",
        read_only=True
    )

    completed_at = serializers.DateTimeField(
        format="%Y-%m-%d",
        read_only=True
    )

    days_together = serializers.SerializerMethodField()

    def get_days_together(self, obj):
        return (obj.completed_at.date() - obj.started_at.date()).days + 1

    class Meta:
        model = CharacterArchive
        fields = [
            'character_id',
            'char_type',
            'character_name',
            'started_at',
            'completed_at',
            'days_together',
        ]

# GET /characters/archive/
class ArchiveListResponseSerializer(serializers.Serializer):
    characters = ArchivedCharacterItemSerializer(many=True)