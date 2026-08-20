import random
from collections import defaultdict

from rest_framework import serializers
from .models import Cycle
from logs.models import PlusLog
from quest.models import Quest

from django.utils import timezone

####### 싸이클 분석 결과 제공 #######
class CycleAnalysisSerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(source = 'id', read_only = True)
    cycle_count = serializers.IntegerField(source = 'count', read_only = True)

    active_days = serializers.SerializerMethodField()
    rest_days = serializers.SerializerMethodField()

    activity_analysis = serializers.SerializerMethodField()
    personalized_analysis = serializers.SerializerMethodField()

    top_plus_logs = serializers.SerializerMethodField()
    completed_quests = serializers.SerializerMethodField()

    log_dates = serializers.SerializerMethodField()
    quest_dates = serializers.SerializerMethodField()

    analysis_request_count = serializers.SerializerMethodField()

    class Meta:
        model = Cycle
        fields = ['cycle_id', 'cycle_count', 'active_days', 'started_at', 'rest_started_at', 'closed_at',
                  'rest_days', 'activity_analysis', 'personalized_analysis', 'top_plus_logs', 'completed_quests',
                  "log_dates", "quest_dates", "analysis_request_count"]

    def get_active_days(self, obj):
        if not obj.started_at:
            return None

        if obj.rest_started_at:
            return (obj.rest_started_at - obj.started_at).days

        today = timezone.localdate()

        return (today - obj.started_at).days

    def get_rest_days(self, obj):
        if not obj.rest_started_at or not obj.closed_at:
            return 0
        return (obj.closed_at - obj.rest_started_at).days

    def _get_analysis(self, obj):
        return obj.analysis if isinstance(obj.analysis, dict) else {}

    def get_activity_analysis(self, obj):
        return self._get_analysis(obj).get('activity_analysis', [])

    def get_personalized_analysis(self, obj):
        return self._get_analysis(obj).get('personalized_analysis', [])
    
    '''
    [AI분석 형태]
        {
        "activity_analysis": [
            "1번째 문장",
            "2번째 문장",
            "3번째 문장"
        ],
        "personalized_analysis": [
            "1번째 문장",
            "2번째 문장",
            "3번째 문장"
        ],
        }'''

    def get_top_plus_logs(self, obj):
        logs = PlusLog.objects.filter(
            cycle=obj, deleted_at__isnull=True, asset__isnull=False
        ).select_related('asset')

        contents_by_asset = defaultdict(list)
        for log in logs:
            contents_by_asset[log.asset.asset_name].append(log.content)

        ranked_assets = sorted(
            contents_by_asset.items(), key=lambda item: len(item[1]), reverse=True
        )[:5]

        return [
            {
                "asset": asset_name,
                "plus_log_count": len(contents),
                "plus_log_content": random.choice(contents),
            }
            for asset_name, contents in ranked_assets
        ]

    def get_completed_quests(self, obj):
        quests = obj.quests.filter(state=Quest.State.DONE).order_by('-last_checked')
        return [q.quest_content for q in quests]

    def get_log_dates(self, obj):
        logs = PlusLog.objects.filter(
        cycle=obj
        ).order_by('-created_at')
        return [log.created_at.date().isoformat() for log in logs]

    def get_quest_dates(self, obj):
        quests = obj.quests.filter(state=Quest.State.DONE).order_by('last_checked')
        return list(dict.fromkeys(
        q.last_checked.isoformat()
        for q in quests
        if q.last_checked
        ))

    def get_analysis_request_count(self, obj):
        return obj.analysis_request_count

class CycleHistorySerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(source = 'id', read_only = True)
    cycle_count = serializers.IntegerField(source = 'count', read_only = True)

    class Meta:
        model = Cycle
        fields = ['cycle_id', 'cycle_count', 
                  'started_at', 'closed_at']