from rest_framework import serializers
from .models import Quest
from weekly_card.models import RecommendedQuest
from datetime import date

####### 퀘스트 시작 #######

#POST 요청 body용
class QuestCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Quest
        fields = ['quest_content']

#POST 요청의 응답 body용
class QuestResponseSerializer(serializers.ModelSerializer):
    quest_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = Quest
        fields = ['quest_id', 'quest_content', 'started_at']

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
                  'days_since_start', 'd_day', 'count', 'state']

    def get_days_since_start(self, obj):
        if not obj.started_at:
            return None
        return (date.today() - obj.started_at).days

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