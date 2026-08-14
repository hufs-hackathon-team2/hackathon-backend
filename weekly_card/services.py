import json
import logging
from django.utils import timezone
from datetime import datetime, time, timedelta, date

from django.conf import settings
from django.db import transaction

from quest.models import Quest
from accounts.models import User
from logs.models import PlusLog 
from weekly_card.models import RecommendedQuest, WeeklyAnalysis

logger = logging.getLogger(__name__)

AI_REQUEST_TIMEOUT_SECONDS = 15  # AI 호출 자체의 타임아웃. 배치 전체가 물려있으니 너무 길게 잡지 않기
MAX_RETRIES = 2


class AIAnalysisError(Exception):
    """AI 호출 또는 응답 파싱이 최종적으로 실패했을 때"""
    pass


# ────────────────────────────────────────────────
# 1. 입력 데이터 조립 (AI에게 뭘 넘길지)
# ────────────────────────────────────────────────

def _collect_weekly_stats(user, week_start: date, week_end: date) -> dict:
    """
    AI 프롬프트에 넣을 원본 데이터를 모으는 부분.
    TODO: PlusLog 개수, 완료 퀘스트 목록, 디바이스 헬스 데이터를 이 기간 기준으로 집계
          (이전에 만든 get_succeeded_quests 등 기존 조회 함수 재사용 가능)
    """
    succeeded_quests = Quest.objects.filter(
        cycle__user=user,  # 실제 User FK 연결 후 이 필터가 맞는지 확인 필요
        state=Quest.State.DONE,
        last_checked__range=(week_start, week_end),
    )
    
    plus_logs = PlusLog.objects.filter(
        user=user, created_at__date__gte=week_start,
        created_at__date__lt=week_end
        )


    return {
        "quest_titles": [q.quest_content for q in succeeded_quests],
        "plus_logs": [log.content for log in plus_logs],
    }


# ────────────────────────────────────────────────
# 2. AI 호출 (인터페이스 계약: 입력/출력 고정)
# ────────────────────────────────────────────────

def _call_ai_weekly_analysis(stats: dict) -> dict:

    import openai  # 지연 import: 배치 진입 시에만 로드되도록

    client = openai.OpenAI(
        api_key=settings.OPEN_AI_API_KEY,
        timeout=AI_REQUEST_TIMEOUT_SECONDS,
    )

    system_prompt = """
    당신은 사용자의 '헬시 플레저(Healthy Pleasure)' 라이프스타일 지속을 돕는 웰니스 파트너입니다.
    사용자가 부담 없이, 즐겁게 건강 습관을 이어갈 수 있도록 응원하고 다음 스텝을 제안하는 것이 목표입니다.

    [톤 & 태도 원칙]
    - 훈계하거나 평가하지 않습니다. 잘한 점을 먼저 인정하고, 부족한 부분은 "그럴 수 있다"는 태도로 부드럽게 언급합니다.
    - 기록이 적거나 실패한 퀘스트가 있어도 절대 죄책감을 유발하지 않습니다. 이탈(앱 이탈, 습관 포기)을 막는 것이 최우선입니다.
    - 문장은 짧고 다정하게, 존댓말을 사용하되 딱딱하지 않게 작성합니다.
    - 이모지는 사용하지 않습니다.

    [작성 항목]
    1. "이번 주 한 줄 총평"
    - 이번 주 PLUS Log 기록과 성공한 작심삼일 퀘스트 내용을 근거로 작성합니다.
    - 반드시 사용자의 실제 행동에 기반한 구체적인 문장이어야 하며, 뻔한 응원 문구("파이팅!")만 반복하지 않습니다.
    - 40자 내외, 한 문장으로 작성합니다.

    2. "다음 주 추천 퀘스트" 5개
    - 이번 주 PLUS Log 내용과 성공한 퀘스트를 기반으로, 자연스럽게 이어갈 수 있는 신체 건강 관련 행동을 추천합니다.
    - 이미 성공한 퀘스트와 완전히 동일한 항목은 다시 추천하지 않되, 난이도를 살짝 올리거나 연계된 행동은 추천 가능합니다.
    - 부담스럽지 않고 하루 안에 실행 가능한 수준으로 작성합니다 (예: "물 하루 8잔 마시기", "저녁 산책 10분").
    - 각 퀘스트는 title(12자 이내, 행동 중심)과 subtitle(15자 내외, 동기부여/근거 한 줄)로 구성합니다.
    - subtitle은 반드시 사용자의 이번 주 기록과 연결지어 작성합니다. (예: 지난주에 잘했던 것과 연관, 혹은 자연스러운 다음 단계)
    - 5개는 서로 겹치지 않는 다른 영역(수분, 활동량, 수면, 스트레칭, 식습관 등)에서 고르게 제안합니다.

    3. "휴식 시작 문구" (rest_message)
    - 사용자가 휴식을 시작했을 때 보여줄 문구입니다.
    - 이번 주 PLUS Log 기록 및 성공한 퀘스트가 있다면, 그 내용을 자연스럽게 언급하며 "그동안의 기록/노력이 사라지지 않는다"는 안심을 줍니다.
    - 기록이 거의 없던 주라면, 죄책감을 주지 않고 "괜찮다, 원할 때 다시 시작하면 된다"는 톤으로 작성합니다.
    - 절대 복귀를 재촉하거나 "다시 열심히 해봐요" 같은 압박성 표현을 쓰지 않습니다.
    - 30~50자, 한 문장 또는 두 문장.
    - 실제 기록/퀘스트명을 최소 1개 이상 자연스럽게 녹여서, 반드시 개인화가 되도록 작성합니다.

    [출력 형식]
    반드시 아래 JSON 형식으로만 응답하십시오. 다른 설명, 마크다운, 코드블록 없이 순수 JSON만 출력합니다.

    {
    "weekly_summary": "string",
    "recommended_quests": [
        {"title": "string", "subtitle": "string"},
        {"title": "string", "subtitle": "string"},
        {"title": "string", "subtitle": "string"},
        {"title": "string", "subtitle": "string"},
        {"title": "string", "subtitle": "string"}
    ],
    "rest_NT_content": "string"
    }
    """

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
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
            # AI가 유효하지 않은 JSON을 반환한 경우 - 재시도 대상
            last_error = e
            logger.warning("AI 응답 JSON 파싱 실패 (attempt %d): %s", attempt, e)

        except Exception as e:
            # 네트워크/타임아웃 등 - 재시도 대상
            last_error = e
            logger.warning("AI 호출 실패 (attempt %d): %s", attempt, e)

    raise AIAnalysisError(f"AI 호출 {MAX_RETRIES}회 재시도 후 최종 실패: {last_error}")


# ────────────────────────────────────────────────
# 3. 결과 저장
# ────────────────────────────────────────────────

def generate_weekly_analysis(user, week_start: date) -> WeeklyAnalysis | None:
    """
    특정 유저의 위클리 분석을 생성하고 DB에 저장.
    이미 이번 주 분석이 있으면(UniqueConstraint) 건너뜀.

    반환: 생성된 WeeklyAnalysis, 이미 존재하거나 실패 시 None
    """
    week_end = week_start + timedelta(days=6)

    if WeeklyAnalysis.objects.filter(
        user_id_placeholder=user.id, week_start=week_start
    ).exists():
        return None

    stats = _collect_weekly_stats(user, week_start, week_end)

    try:
        ai_result = _call_ai_weekly_analysis(stats)
    except AIAnalysisError:
        logger.error("유저 %s 위클리 분석 실패, 이번 주는 건너뜀", user.id)
        return None  # 이 유저만 스킵하고 배치는 계속 진행

    with transaction.atomic():
        analysis = WeeklyAnalysis.objects.create(
            user_id_placeholder=user.id,
            week_start=week_start,
            week_end=week_end,
            analysis=ai_result.get("weekly_summary", ""),
            rest_NT_content=ai_result.get("rest_message", "")
            # TODO: plus_log_count, success_quest_count, active_days 채우기 (stats에서)
        )

        for item in ai_result.get("recommended_quests", []):
            RecommendedQuest.objects.create(
                weekly_analysis=analysis,
                quest_content=item["quest_content"],
                reason=item.get("reason"),
            )

    return analysis


# ────────────────────────────────────────────────
# 4. 배치 진입점 (management command에서 호출)
# ────────────────────────────────────────────────

def run_weekly_batch(week_start: date) -> None:

    all_users = User.objects.all()
    week_start = date.today() -timedelta(days=6)

    for user in all_users:
        count_plus_logs = Plus_Log.objects.filter( #TODO: 실제 플러스로그 모델과 연결 필요 
            user=user,
            created_at__gte=week_start,
            created_at__lte=date.today()).count()

        if count_plus_logs < 3: continue

        try:
            generate_weekly_analysis(user, week_start)

        except Exception:
            logger.exception(
                "Weekly analysis failed for user_id=%s (week_start=%s)",
                user.id, week_start,
            )
            continue