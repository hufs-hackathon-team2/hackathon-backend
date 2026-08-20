from rest_framework import serializers
from .models import WeeklyAnalysis, RecommendedQuest
from logs.models import PlusLog
from quest.models import Quest

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

    active_days = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyAnalysis
        fields = ['week_start', 'week_end',
                  'plus_log_count', 'success_quest_count',
                  'active_days', 'weekly_summary',
                  'next_week_recommendations', 'rest_NT_content', 'is_generated']

    def get_is_generated(self, obj):
        return self.context.get('is_generated', False)

    def get_active_days(self, obj):
        log_dates = PlusLog.objects.filter(
            user=obj.user,
            created_at__date__gte=obj.week_start,
            created_at__date__lte=obj.week_end,
        ).values_list('created_at__date', flat=True)

        quest_dates = Quest.objects.filter(
            cycle__user=obj.user,
            state=Quest.State.DONE,
            last_checked__range=(obj.week_start, obj.week_end),
        ).values_list('last_checked', flat=True)

        return len(set(log_dates) | set(quest_dates))
