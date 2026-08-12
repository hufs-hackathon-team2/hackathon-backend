# cycle_services.py
from datetime import date
from django.utils import timezone
from .models import User, Cycle, PlusLog, Quest


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


def check_and_apply_rest_transition(user: User, today: date, source: str) -> bool:
    """
    [C3/C4] ACTIVE -> RESTING

    source: "batch" (매일 밤 자동 점검) | "app_entry" (앱 진입 시 보정)

    가드: user.cycle_status == ACTIVE AND (today - last_record_date).days >= 7

    처리:
    - user.current_cycle_status -> RESTING
    - 현재 Cycle에 휴식 시작일 기록
    - 휴식기 알림 발송 + 발송 시각 기록 (C3, C4 동일 처리)

    반환: 전환이 실제로 일어났는지 여부
    """
    pass


def close_and_start_new_cycle(user: User, trigger_date: date, linked_record=None) -> Cycle | None:
    """
    [C5/C8 -> C6] RESTING -> CLOSED -> ACTIVE (하나의 트랜잭션)

    trigger: plus log 저장(C5) 또는 퀘스트 시작(C8)

    가드: user.cycle_status == RESTING 인 경우에만 실행
          (RESTING -> ACTIVE 직접 전환 금지, 반드시 CLOSED를 거침)

    처리:
    - 기존 Cycle: ended_at = trigger_date, status = CLOSED
    - 지난 사이클 분석 요청 트리거
    - 새 Cycle 생성 (started_at = trigger_date, status = ACTIVE)
    - linked_record(방금의 log/quest)를 새 사이클에 연결
    - user.cycle_status -> ACTIVE

    반환: 새로 생성된 Cycle, 조건 미충족 시 None
    """
    


def handle_app_entry(user: User, today: date) -> bool:
    """
    [C4/C7] 앱 진입 시 호출.

    - user.cycle_status == ACTIVE 이고 7일 경과 -> check_and_apply_rest_transition 호출 (C4)
    - user.cycle_status == RESTING -> 아무것도 하지 않고 그대로 유지 (C7)
      (금지 전이: 앱 진입만으로 RESTING 종료 불가)

    반환: RESTING으로 전환되었는지 여부
    """
    current_cycle = user.current_cycle

    if current_cycle and current_cycle.status == 'ACTIVE':
        return check_and_apply_rest_transition(user, today, 'app_entry')

    return False


def get_resume_screen_data(user: User) -> dict:
    """
    [CY-05] C6 직후 노출되는 재개 팝업 데이터 구성.

    - 제목/서브텍스트는 고정 문구
    - 직전 성공(DONE) 퀘스트 조회 -> 추천 문구에 삽입
    - 성공 퀘스트가 없는 경우의 fallback 문구 처리 필요
    """
    pass