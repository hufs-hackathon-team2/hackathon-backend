# cycle_services.py
from datetime import date, timedelta
from django.utils import timezone
from .models import Cycle
from django.db import transaction
from quest.models import Quest
from accounts.models import User
from logs.models import PlusLog
from django.conf import settings
from weekly_card.services import AIAnalysisError
import json
import logging

logger = logging.getLogger(__name__)

AI_REQUEST_TIMEOUT_SECONDS = 15  # AI 호출 자체의 타임아웃. 배치 전체가 물려있으니 너무 길게 잡지 않기
MAX_RETRIES = 2

######### 범용 함수 #########

def get_last_record_date(user: User) -> date | None:
    #해당 유저의 플러스로그 마지막 기록일, 작심삼일퀘스트 마지막 시작일/체크일 조회
    #그중에서 가장 최근 날짜가 최근 기록일이 됨
    last_plus_log = PlusLog.objects.filter(user=user).order_by("-created_at").first()
    last_quest_start = Quest.objects.filter(cycle__user=user).order_by("-started_at").first()
    last_quest_check = Quest.objects.filter(cycle__user=user).order_by("-last_checked").first()

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
    succeeded_quests = Quest.objects.filter(cycle=cycle, state=Quest.State.DONE)

    return [quest.quest_content for quest in succeeded_quests]



######### 상태 전이 및 기능 구현 #########

def check_and_apply_rest_transition(user: User, today: date) -> bool:
    """
    상태 전이: [C3/C4] ACTIVE -> RESTING
    기능 코드: CY-01 - 휴식기 판정

]   TODO: 휴식기 알림 발송 + 발송 시각 기록 (C3, C4 동일 처리)
    """
    last_record_date = get_last_record_date(user)
    current_cycle = user.current_cycle

    if not last_record_date or not current_cycle:
        return False

    if current_cycle.state != Cycle.State.ACTIVE:
        return False

    if (today - last_record_date).days < 7:
        return False

    current_cycle.state = Cycle.State.RESTING
    current_cycle.rest_started_at = today
    current_cycle.save(update_fields=['state', 'rest_started_at'])

    # TODO: 휴식기 알림 발송 + 발송 시각 기록 (C3, C4 동일 처리)

    return True


def close_and_start_new_cycle(user: User, trigger_date: date, linked_record: PlusLog | Quest | None) -> Cycle | None:
    """
    상태 전이: [C5/C8 -> C6] RESTING -> CLOSED -> ACTIVE (하나의 트랜잭션)
    기능 코드: CY-01 - 사이클 종료 / CY-05 - 사이클 재개

    trigger: plus log 저장(C5) - TODO: 유민님 연결 필요
             or 퀘스트 시작(C8) - TODO
    """
    current_cycle = user.current_cycle

    if not current_cycle or current_cycle.state != Cycle.State.RESTING:
        return None

    with transaction.atomic():
        current_cycle.state=Cycle.State.CLOSED
        current_cycle.closed_at=trigger_date - timedelta(days=1)
        current_cycle.save(update_fields=['state', 'closed_at'])

        #TODO: 지난 사이클 분석 요청 트리거

        new_cycle = Cycle.objects.create(
            user=user, state=Cycle.State.ACTIVE, 
            started_at=trigger_date, count = current_cycle.count+1
        )

        user.current_cycle = new_cycle
        user.save(update_fields=['current_cycle'])

        if linked_record is not None:
            linked_record.cycle = new_cycle
            linked_record.save(update_fields=['cycle'])

        return new_cycle


def handle_app_entry(user: User, today: date) -> bool:
    """
    상태 전이: [C4/C7] 앱 진입 시 호출.
    """
    current_cycle = user.current_cycle

    if current_cycle and current_cycle.state == Cycle.State.ACTIVE:
        return check_and_apply_rest_transition(user, today)

    return False


def start_cycle_after_onboarding(user: User, today: date) -> Cycle | None:
    """
    상태 전이: [C1] 온보딩 후 첫번째 로그 기록 or 퀘스트 시작
    """

    if user.current_cycle is not None:
        return None

    with transaction.atomic():
        
        new_cycle = Cycle.objects.create(
            user=user, 
            state=Cycle.State.ACTIVE, 
            started_at=today
        )

        user.current_cycle = new_cycle
        user.save(update_fields=['current_cycle'])

    return new_cycle



def _collect_cycle_stats(cycle: Cycle) -> dict:

    succeeded_quests = get_succeeded_quests(cycle)

    plus_logs = PlusLog.objects.filter(cycle=cycle)
    plus_logs = [log.content for log in plus_logs]

    return {
        "quest_titles": succeeded_quests,
        "plus_logs": plus_logs,
    }



def _call_ai_cycle_analysis(stats: dict) -> dict:

    import openai

    client = openai.OpenAI(
        api_key=settings.OPEN_AI_API_KEY,
        timeout=AI_REQUEST_TIMEOUT_SECONDS
    )

    system_prompt = """
    당신은 사용자의 '헬시 플레저(Healthy Pleasure)' 라이프스타일 지속을 돕는 웰니스 파트너입니다.
    사용자가 부담 없이, 즐겁게 건강 습관을 이어갈 수 있도록 응원하고 다음 스텝을 제안하는 것이 목표입니다.

    이 앱에서 사용자는 Plus Log(헬시 플레저에 도움이 되는 행동을 기록하는 로그)와 작심삼일 퀘스트를 수행하며 기록을 이어갑니다.
    7일 이상 기록이 없으면 현재 '헬시 사이클'은 휴식기로 전환되고, 휴식기 중 새로운 기록이 발생하면 다음 사이클이 시작됩니다.
    이를 통해 기록의 중단이 결코 포기가 아니라, 하나의 사이클 안에 자연스럽게 포함되는 '휴식'으로 받아들여지도록 돕습니다.

    [톤 & 태도 원칙]
    - 훈계하거나 평가하지 않습니다. 잘한 점을 먼저 인정하고, 부족한 부분은 "그럴 수 있다"는 태도로 부드럽게 언급합니다.
    - 기록이 적거나 실패한 퀘스트가 있어도 절대 죄책감을 유발하지 않습니다. 이탈(앱 이탈, 습관 포기)을 막는 것이 최우선입니다.
    - 문장은 짧고 다정하게, 존댓말을 사용하되 딱딱하지 않게 작성합니다.
    - 이모지는 사용하지 않습니다.

    [작성 항목]
    1. "해당 사이클의 활동에 대한 AI 분석" 3문장
    - 해당 사이클의 PLUS Log 기록과 성공한 작심삼일 퀘스트 내용을 근거로 작성합니다.
    - 반드시 사용자의 실제 행동에 기반한 구체적인 문장이어야 합니다.

    2. 1번 항목에 따른 개인화 분석 3문장
    - 1번에서 언급한 사실을 단순 반복하지 말고, 그 안에서 드러나는 사용자만의 패턴이나 의미를 짚어냅니다.
      (예: 기록을 남기는 시간대, 자주 선택한 활동 유형, 꾸준함이 두드러진 요일, 특정 퀘스트에 대한 선호 등)
    - 수치나 사실을 근거로 "왜 그런 흐름이 나타났을지"를 사용자 입장에서 다정하게 해석해줍니다. 단정적인 원인 진단이 아니라, 공감하는 어조로 짐작하는 수준으로 작성합니다.
    - 활동이 적었거나 중단된 흐름이 있어도 실패로 규정하지 않고, 그 자체를 그 사람의 리듬이나 사정으로 받아들이는 문장으로 작성합니다. 절대 지적하거나 개선을 종용하는 어조를 쓰지 않습니다.
    - 사용자가 "내 이야기를 하고 있다"고 느낄 만큼 구체적으로 작성하되, 근거 없는 성격 단정이나 심리 분석(예: "당신은 완벽주의 성향이 있어요")은 하지 않습니다.
    
    [출력 형식]
    반드시 아래 JSON 형식으로만 응답하십시오. 다른 설명, 마크다운, 코드블록 없이 순수 JSON만 출력합니다.

    {
        "activity_analysis": [
            "string", "string", "string"
        ],
        "personalized_analysis": [
            "string", "string", "string"
        ]
    }
    """

    last_error = None

    for attempt in range(1, MAX_RETRIES+1):

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(stats, ensure_ascii=False)},
                ],
            )
            raw_text = response.choices[0].message.content
            return json.loads(raw_text)

        except json.JSONDecodeError as e:
            last_error = e
            logger.warning("AI 응답 JSON 파싱 실패 (attempt %d): %s", attempt, e)

        except Exception as e:
            last_error = e
            logger.warning("AI 호출 실패 (attempt %d): %s", attempt, e)

    raise AIAnalysisError(f"AI 호출 {MAX_RETRIES}회 재시도 후 최종 실패: {last_error}")