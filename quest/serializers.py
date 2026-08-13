from rest_framework import serializers
from .models import Quest

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