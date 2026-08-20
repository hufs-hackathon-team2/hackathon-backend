from rest_framework import serializers
from .models import Quest
from weekly_card.models import RecommendedQuest
from django.utils import timezone
from characters.models import CharacterGrowthEvent
from django.shortcuts import get_object_or_404

####### 퀘스트 시작 #######

#POST 요청 body용
class QuestCreateSerializer(serializers.ModelSerializer):
    quest_content = serializers.CharField(
        max_length=199,      # len(quest_content) >= 200 차단 (199자까지만 허용)
        allow_blank=False,   # 빈 문자열("") 차단
        trim_whitespace=True, # 앞뒤 공백 자동 제거

        error_messages={
            'blank': '퀘스트 내용이 비어있습니다. 올바르게 입력해주세요.',
            'max_length': '퀘스트 내용이 200자를 초과합니다.'
        }
    )
    class Meta:
        model = Quest
        fields = ['quest_content']

#POST 요청의 응답 body용
class QuestResponseSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source='id', read_only=True)
    new_cycle_started = serializers.SerializerMethodField()

    class Meta:
        model = Quest
        fields = ['quest_id', 'quest_content', 
                  'started_at', 'new_cycle_started']

    def get_new_cycle_started(self, obj):
        return self.context.get('new_cycle_started', False)

####### 퀘스트 수행 체크 #######
class CheckQuestSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Quest
        fields = ['quest_id', 'state', 'count', 'last_checked', 'quest_content']

####### 퀘스트 포기 #######
class AbandonQuestSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Quest
        fields = ['quest_id', 'state', 'count']

####### 현재 퀘스트 조회 #######
class CurrentQuestSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source='id', read_only=True)

    days_since_start = serializers.SerializerMethodField()
    d_day = serializers.SerializerMethodField()

    class Meta:
        model = Quest
        fields = ['quest_id', 'quest_content', 'started_at',
                  'days_since_start', 'd_day', 'count', 
                  'state', 'last_checked']

    def get_days_since_start(self, obj):
        if not obj.started_at:
            return None
        return (timezone.localdate() - obj.started_at).days

    def get_d_day(self, obj):
        days = self.get_days_since_start(obj)
        if days is None:
            return None
        return 7 - days

class AIRecommendedQuestSerializer(serializers.ModelSerializer):
    recommendation_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = RecommendedQuest
        fields = ['recommendation_id', 'quest_content', 'reason']

class AIRecommendationResponseSerializer(serializers.Serializer):
    has_recommendations = serializers.BooleanField()
    week_start = serializers.DateField()

    recommended_quests = AIRecommendedQuestSerializer(many=True)

    plus_log_count = serializers.IntegerField()
    required_log_count = serializers.IntegerField()

class AllQuestsOfCycleSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source = 'id', read_only = True)

    class Meta:
        model = Quest
        fields = ['quest_id', 'quest_content', 'state', 
                  'started_at', 'last_checked', 'count']

class AllQuestsOfCycleResponseSerializer(serializers.Serializer):
    cycle_id = serializers.IntegerField()
    quests = AllQuestsOfCycleSerializer(many = True)


class QuestSuccessDetailSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source = 'id', read_only = True)

    is_completed = serializers.SerializerMethodField()
    character_gauge_gained = serializers.SerializerMethodField()
    character_gauge_total = serializers.SerializerMethodField()

    class Meta:
        model = Quest
        fields = ['quest_id', 'state', 'count',
                  'is_completed', 'quest_content',
                  'character_gauge_gained', 'character_gauge_total']

    def get_is_completed(self, obj):
        return obj.state == Quest.State.DONE

    def get_character_gauge_gained(self, obj):
        generated_growth_event = CharacterGrowthEvent.objects.filter(
            quest=obj).order_by('-created_at').first()

        return generated_growth_event.score if generated_growth_event else 0

    def get_character_gauge_total(self, obj):
        character = obj.cycle.user.character_state

        return character.total_score