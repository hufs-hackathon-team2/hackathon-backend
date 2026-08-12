# cycle_services.py
from datetime import date
from django.utils import timezone
from .models import User, Cycle, PlusLog, Quest
from django.db import transaction

######### 범용 함수 #########

def get_last_record_date(user: User) -> date | None:
    #해당 유저의 플러스로그 마지막 기록일, 작심삼일퀘스트 마지막 시작일/체크일 조회
    #그중에서 가장 최근 날짜가 최근 기록일이 됨
    last_plus_log = PlusLog.objects.filter(user=user).order_by("-created_at").first()
    last_quest_start = Quest.objects.filter(user=user).order_by("-started_at").first()
    last_quest_check = Quest.objects.filter(user=user).order_by("-last_checked").first()

    candidates = [
        last_plus_log.created_at.date() if last_plus_log else None,
        last_quest_start.started_at.date() if last_quest_start else None,
        last_quest_check.last_checked.date() if last_quest_check else None
    ]

    candidates = [d for d in candidates if d is not None]

    return max(candidates) if candidates else None

def get_succeeded_quests(cycle: Cycle) -> list:
    """
    특정 사이클의 성공(DONE) 퀘스트 내용 목록 조회.
    사용처: 재개 화면(CY-05), 사이클 종료 자동 분석(C5/C8), 사용자 분석 요청
    """
    succeeded_quests = Quest.objects.filter(cycle_id=cycle.id, state='DONE')

    return [quest.quest_content for quest in succeeded_quests]


######### 상태 전이 및 기능 구현 #########

def check_and_apply_rest_transition(user: User, today: date) -> bool:
    """
    상태 전이: [C3/C4] ACTIVE -> RESTING
    기능 코드: CY-01 - 휴식기 판정

    가드: current_cycle.state == ACTIVE AND (today - last_record_date).days >= 7

    처리:
    - current_cycle.state -> RESTING
    - 현재 Cycle에 휴식 시작일 기록
    - TODO: 휴식기 알림 발송 + 발송 시각 기록 (C3, C4 동일 처리)

    반환: 전환이 실제로 일어났는지 여부
    """
    last_record_date = get_last_record_date(user)
    current_cycle = user.current_cycle

    if last_record_date and current_cycle:
        if current_cycle.state == 'ACTIVE' and (today - last_record_date).days >= 7:
            current_cycle.state = 'RESTING'          
            current_cycle.rest_started_at = today
            current_cycle.save(update_fields=['state', 'rest_started_at'])

            #TODO: 휴식기 알림 발송 + 발송 시각 기록 (C3, C4 동일 처리)

            return True
          
        else: return False
    else:
        return False


def close_and_start_new_cycle(user: User, trigger_date: date, linked_record=None) -> Cycle | None:
    """
    상태 전이: [C5/C8 -> C6] RESTING -> CLOSED -> ACTIVE (하나의 트랜잭션)
    기능 코드: CY-01 - 사이클 종료 / CY-05 - 사이클 재개

    trigger: plus log 저장(C5) - 유민님 연결 필요
             or 퀘스트 시작(C8)

    가드: user.cycle_state == RESTING 인 경우에만 실행
          (RESTING -> ACTIVE 직접 전환 금지, 반드시 CLOSED를 거침)

    처리:
    - 기존 Cycle: ended_at = trigger_date - 1, state = CLOSED
    - 지난 사이클 분석 요청 트리거
    - 새 Cycle 생성 (started_at = trigger_date, state = ACTIVE)
    - linked_record(방금의 log/quest)를 새 사이클에 연결
    - user.cycle_state -> ACTIVE

    반환: 새로 생성된 Cycle, 조건 미충족 시 None
    """
    current_cycle = user.current_cycle

    if not current_cycle or current_cycle.state != 'RESTING':
        return None

    with transaction.atomic():
        current_cycle.state='CLOSED'
        current_cycle.closed_at=trigger_date - 1
        current_cycle.save(update_fields=['state', 'closed_at'])

        #TODO: 지난 사이클 분석 요청 트리거

        new_cycle = Cycle.objects.create(
            user_ID=user, state='ACTIVE', 
            started_at=trigger_date, count = current_cycle.count+1
        )

        #TODO: linked_record를 new_cycle에 연결
        user.current_cycle = new_cycle
        user.save(update_fields=['current_cycle'])

        return new_cycle


def handle_app_entry(user: User, today: date) -> bool:
    """
    상태 전이: [C4/C7] 앱 진입 시 호출.

    - current_cycle.state == ACTIVE 이고 7일 경과 -> check_and_apply_rest_transition 호출 (C4)
    - current_cycle.state == RESTING -> 아무것도 하지 않고 그대로 유지 (C7)
      (금지 전이: 앱 진입만으로 RESTING 종료 불가)

    반환: RESTING으로 전환되었는지 여부
    """
    current_cycle = user.current_cycle

    if current_cycle and current_cycle.state == 'ACTIVE':
        return check_and_apply_rest_transition(user, today, 'app_entry')

    return False


def start_cycle_after_onboarding(user: User, today: date) -> Cycle | None:
    """
    상태 전이: [C1] 온보딩 후 첫번째 로그 기록 or 퀘스트 시작
    """

    if user.current_cycle is not None:
        return None

    with transaction.atomic():
        
        new_cycle = Cycle.objects.create(
            user_ID=user, state='ACTIVE', 
            started_at=today, count = 1
        )

        user.current_cycle = new_cycle
        user.save(update_fields=['current_cycle'])

    return new_cycle
