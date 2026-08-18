from rest_framework import serializers
from .models import Cycle
from logs.models import PlusLog
from quest.models import Quest

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
                  'rest_days', 'activity_analysis', 'personalized_analysis', 'completed_quests',
                  "log_dates", "quest_dates", "analysis_request_count"]

    def get_active_days(self, obj):
        if not obj.started_at or not obj.rest_started_at:
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

#TODO: 퀘스트/플러스로그 내용 구분...? 상위 10개/5개 판단 기준 정하고 로직 구현해야 함 

    def get_top_plus_logs(self, obj):
        logs = PlusLog.objects.filter(
        cycle=obj
        ).order_by('-created_at')[:10]
        return [log.content for log in logs]

    def get_completed_quests(self, obj):
        quests = obj.quests.filter(state=Quest.State.DONE)[:5]
        return [q.quest_content for q in quests]

    def get_log_dates(self, obj):
        logs = PlusLog.objects.filter(
        cycle=obj
        ).order_by('-created_at')
        return [log.created_at.date().isoformat() for log in logs]

    def get_quest_dates(self, obj):
        quests = obj.quests.filter(state=Quest.State.DONE).order_by('last_checked')
        return list(dict.fromkeys(
        q.last_checked.date().isoformat()
        for q in quests
        if q.last_checked
        ))

    def get_analysis_request_count(self, obj):
        return obj.analysis_request_count


    #GET 요청에서는 analysis_request_count 필드를 제거
    def to_representation(self, instance):
        # 1. 먼저 기존 필드들이 모두 담긴 딕셔너리 데이터를 가져옵니다.
        data = super().to_representation(instance)
        
        # 2. 현재 요청이 'GET' 인지 확인합니다.
        request = self.context.get('request')
        if request and request.method == 'GET':
            # 3. 'GET' 요청이라면 딕셔너리에서 해당 필드를 완전히 삭제(pop)합니다.
            data.pop('analysis_request_count', None)
            
        return data

class CycleHistorySerializer(serializers.ModelSerializer):
    cycle_id = serializers.IntegerField(source = 'id', read_only = True)
    cycle_count = serializers.IntegerField(source = 'count', read_only = True)

    class Meta:
        model = Cycle
        fields = ['cycle_id', 'cycle_count', 
                  'started_at', 'closed_at']