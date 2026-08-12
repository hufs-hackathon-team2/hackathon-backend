from rest_framework import serializers
from .models import Quest

### 퀘스트 시작 ###

#POST 요청 body용
class QuestCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Quest
        fields = ['quest_content']

#POST 요청의 응답 body용
class QuestResponseSerializer(serializers.ModelSerializer):

    class Meta:
        model = Quest
        fields = ['id', 'quest_content', 'started_at']