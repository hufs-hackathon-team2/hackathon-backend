from rest_framework import serializers
from .models import WeeklyAnalysis, RecommendedQuest

class NextWeekQuestsSerializer(serializers.ModelSerializer):
    recommendation_id = serializers.IntegerField(source = 'id', read_only = True)

    class Meta:
        model = RecommendedQuest
        fields = ['recommendation_id', 'quest_content', 'reason']

class WeeklyCardSerializer(serializers.ModelSerializer):
    next_week_recommendations = NextWeekQuestsSerializer(
        source = 'recommendations', many=True)

    weekly_summary = serializers.CharField(
        source='analysis.weekly_summary'
    )

    is_generated = serializers.SerializerMethodField()
    
    class Meta:
        model = WeeklyAnalysis
        fields = ['week_start', 'week_end',
                  'plus_log_count', 'success_quest_count',
                  'active_days', 'weekly_summary',
                  'next_week_recommendations', 'rest_NT_content', 'is_generated']

    def get_is_generated(self, obj):
        return self.context.get('is_generated', False)
