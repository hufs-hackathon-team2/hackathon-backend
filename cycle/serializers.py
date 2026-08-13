from rest_framework import serializers
from .models import Cycle

####### 이전 싸이클 분석 결과 제공 #######
class FormerCycleAnalysisSerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(source = 'id', read_only = True)
    cycle_count = serializers.IntegerField(source = 'count', read_only = True)

    active_days = serializers.SerializerMethodField()
    rest_days = serializers.SerializerMethodField()

    activity_analysis = serializers.SerializerMethodField()
    personalized_analysis = serializers.SerializerMethodField()

    #TODO: top_plus_logs = serializers.SerializerMethodField()
    completed_quests = serializers.SerializerMethodField()

    class Meta:
        model = Cycle
        fields = ['cycle_id', 'cycle_count', 'active_days', 'started_at', 'rest_started_at', 'closed_at',
                  'rest_days', 'activity_analysis', 'personalized_analysis', 'completed_quests']

    def get_active_days(self, obj):
        if not obj.started_at or not obj.closed_at:
            return None
        return (obj.rest_started_at - obj.started_at).days

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

    #TODO: 플러스로그 가져오는 함수

    def get_completed_quests(self, obj):
        quests = obj.quests.filter(state='DONE')
        return [q.quest_content for q in quests]