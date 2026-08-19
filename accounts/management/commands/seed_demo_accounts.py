# 시연 영상용 데모 계정 생성 커맨드.
#
# demo01~demoNN@example.com 계정을 만들고, 각 계정에 약 3개월치 사용 이력(사이클 4회,
# 그 중 3회는 종료+AI 분석 완료, 1회는 진행중; 위클리 카드; 작심삼일 퀘스트 성공/진행;
# 플러스 로그; 그에 따른 캐릭터 성장)을 채워 넣는다.
#
# 사이클 종료 분석(cycle.services.generate_cycle_analysis)과 위클리 카드 분석
# (weekly_card.services.generate_weekly_analysis)은 실제 운영 코드를 그대로 호출해서
# 실제 OpenAI API로 생성한다 (--skip-ai를 주면 더미 텍스트로 대체해서 비용/시간 없이
# 파이프라인만 먼저 검증할 수 있다).
import random
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from characters.models import CharacterGrowthEvent, CharacterState
from cycle.models import Cycle
from cycle.services import generate_cycle_analysis
from logs.models import Asset, PlusLog
from quest.models import Quest
from weekly_card.services import generate_weekly_analysis

DEMO_PASSWORD = "Demo1234!"
TOTAL_DAYS_BACK = 90
REST_TRIGGER_DAYS = 7  # cycle.services.check_and_apply_rest_transition과 동일
QUEST_DEADLINE_DAYS = 7  # quest.services.QUEST_DEADLINE_DAYS와 동일

CHAR_NAMES = ["몽이", "콩이", "보리", "두부", "초코", "라떼", "뭉치", "모카", "순두부", "감자"]
INTERESTS = [
    "건강한 습관 만들기", "체력 관리", "다이어트", "수면의 질 개선",
    "물 많이 마시기 습관", "꾸준한 운동 루틴", "식단 관리", "스트레스 관리",
    "아침 루틴 만들기", "체중 관리",
]

# (플러스 로그 내용, logs.constants.ASSET_LIST에 실제 존재하는 asset_name)
LOG_BANK = [
    ("아침에 20분 조깅했다", "run"),
    ("저녁 먹고 동네 산책 30분 다녀옴", "walk"),
    ("헬스장 가서 웨이트 1시간", "weights"),
    ("자기 전 스트레칭 10분", "yoga"),
    ("주말에 수영 다녀왔어요", "swim"),
    ("한강에서 자전거 탔다", "bike"),
    ("주말 등산 다녀옴", "climb"),
    ("오늘 물 8잔 다 채워 마셨다", "water"),
    ("점심에 샐러드로 든든하게", "salad"),
    ("아침에 사과 하나 먹었다", "apple"),
    ("저녁에 생선구이로 단백질 챙김", "fish"),
    ("계란후라이 두 개로 아침 시작", "egg"),
    ("오늘 7시간 푹 잤다", "sleep"),
    ("일찍 일어나서 하루 시작", "sunrise"),
    ("자기 전 반신욕 했음", "bath"),
    ("샤워하고 개운하게 마무리", "shower"),
    ("영양제 챙겨 먹었다", "pill"),
    ("아침 공복에 물 한 잔", "water"),
    ("커피 대신 차 마셨어요", "tea"),
    ("점심 도시락 직접 싸옴", "bento"),
    ("저녁에 견과류 한 줌", "nuts"),
    ("아침 요거트에 블루베리 올려 먹음", "blueberry"),
    ("퇴근 후 요가 클래스 다녀옴", "yoga"),
    ("주말에 배드민턴 쳤다", "badminton"),
    ("친구랑 테니스 한 게임", "tennis"),
    ("집에서 필라테스 20분", "ballet"),
    ("아침 명상 10분 했다", "meditate"),
    ("자기 전 휴대폰 끄고 책 읽음", "book"),
    ("퇴근길에 계단으로 걸어 올라옴", "walk"),
    ("장 보러 가서 채소 왕창 사옴", "shopping"),
    ("오늘 저녁은 집밥으로 든든히", "pot"),
    ("아침 루틴으로 양치까지 완료", "toothbrush"),
    ("하루종일 물병 들고 다녔다", "bottle"),
    ("스쿼트 3세트 했다", "weights"),
    ("저녁 산책하며 햇살 좋았다", "sun"),
]

QUEST_BANK = [
    "하루 물 8잔 마시기",
    "저녁 10분 스트레칭",
    "매일 7시간 이상 수면",
    "아침 공복 유산소 15분",
    "하루 한 끼는 샐러드로",
    "자기 전 휴대폰 끄고 독서 10분",
    "하루 6천보 걷기",
    "아침 기상 후 물 한 잔",
    "간식 대신 과일 먹기",
    "저녁 9시 이후 야식 안 먹기",
    "매일 아침 스트레칭",
    "주 3회 근력 운동",
    "자기 전 반신욕 5분",
    "하루 5분 명상하기",
    "카페인 오후 2시 이후 끊기",
]

DUMMY_CYCLE_ANALYSIS = {
    "activity_analysis": [
        "(더미) 이번 사이클 동안 꾸준히 기록을 남겼어요.",
        "(더미) 특히 활동 기록이 자주 보였어요.",
        "(더미) 작심삼일 퀘스트도 성공적으로 마무리했어요.",
    ],
    "personalized_analysis": [
        "(더미) 꾸준한 리듬이 느껴지는 사이클이었어요.",
        "(더미) 본인만의 페이스를 잘 지켜가고 있어요.",
        "(더미) 이 흐름을 이어가도 좋을 것 같아요.",
    ],
}


def _aware(d: date, hour: int, minute: int) -> datetime:
    return timezone.make_aware(datetime.combine(d, time(hour=hour, minute=minute)))


class Command(BaseCommand):
    help = "시연 영상용 데모 계정(3개월 사용 이력 포함)을 생성한다."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=10, help="생성할 데모 계정 수")
        parser.add_argument("--start-index", type=int, default=1, help="demoNN 시작 번호")
        parser.add_argument(
            "--skip-ai", action="store_true",
            help="실제 OpenAI 호출 없이 더미 텍스트로 채운다 (파이프라인 검증용)",
        )

    def handle(self, *args, **options):
        count = options["count"]
        start_index = options["start_index"]
        skip_ai = options["skip_ai"]
        today = timezone.localdate()

        if not Asset.objects.exists():
            self.stderr.write(self.style.ERROR(
                "logs.Asset 테이블이 비어있습니다. 0004_seed_assets 마이그레이션이 적용됐는지 확인하세요."
            ))
            return

        for i in range(start_index, start_index + count):
            email = f"demo{i:02d}@example.com"
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.WARNING(f"{email} 이미 존재 - 스킵"))
                continue

            user = self._create_user(i, email, today)
            summary = self._seed_history(user, today, skip_ai)
            self.stdout.write(self.style.SUCCESS(
                f"{email} 생성 완료 | 사이클 {summary['cycles']}개 "
                f"(분석 {summary['cycle_analyses']}건) | 위클리카드 {summary['weekly_cards']}개 | "
                f"플러스로그 {summary['logs']}개 | 퀘스트 {summary['quests']}개 "
                f"(성공 {summary['quests_done']}) | 캐릭터 점수 {summary['total_score']}"
            ))

    # ------------------------------------------------------------------
    # 계정 생성
    # ------------------------------------------------------------------
    def _create_user(self, index: int, email: str, today: date) -> User:
        with transaction.atomic():
            char_type = User.CharacterType.CAT if index % 2 else User.CharacterType.DOG
            user = User.objects.create_user(
                email=email,
                password=DEMO_PASSWORD,
                nickname=f"데모{index:02d}",
            )
            user.onboarding_completed = True
            user.character_type = char_type
            user.character_name = CHAR_NAMES[(index - 1) % len(CHAR_NAMES)]
            user.interest = INTERESTS[(index - 1) % len(INTERESTS)]
            user.push_permission_granted = True
            user.save()

            CharacterState.objects.filter(user=user).update(char_type=char_type.upper())

            created_at = _aware(today - timedelta(days=TOTAL_DAYS_BACK), 9, 0)
            User.objects.filter(pk=user.pk).update(created_at=created_at)
            CharacterState.objects.filter(user=user).update(created_at=created_at)

        user.refresh_from_db()
        return user

    # ------------------------------------------------------------------
    # 3개월치 사이클/로그/퀘스트/위클리카드 이력 생성
    # ------------------------------------------------------------------
    def _seed_history(self, user: User, today: date, skip_ai: bool) -> dict:
        char_state = user.character_state
        start_date = today - timedelta(days=TOTAL_DAYS_BACK)

        summary = {
            "cycles": 0, "cycle_analyses": 0, "weekly_cards": 0,
            "logs": 0, "quests": 0, "quests_done": 0, "total_score": 0,
        }

        # 사이클 1~3(종료)용 활동 기간을 먼저 뽑고, 남는 일수를 사이클 4(진행중)에 몰아준다.
        closed_spans = []
        for _ in range(3):
            active_len = random.randint(8, 12)
            gap = REST_TRIGGER_DAYS + random.randint(2, 5)
            closed_spans.append((active_len, gap))

        cursor = start_date
        rng = random.Random(user.user_id)

        for cycle_no, (active_len, gap) in enumerate(closed_spans, start=1):
            window_start = cursor
            window_end = cursor + timedelta(days=active_len - 1)

            cycle = Cycle.objects.create(
                user=user, state=Cycle.State.CLOSED, count=cycle_no,
                started_at=window_start,
            )

            logs_created, quests_created, quests_done = self._populate_activity(
                user, cycle, char_state, window_start, window_end, rng, allow_in_progress=False,
            )
            summary["logs"] += logs_created
            summary["quests"] += quests_created
            summary["quests_done"] += quests_done

            last_record_date = window_end  # 활동 기간 마지막날에는 항상 기록을 남기도록 보장함
            rest_started_at = last_record_date + timedelta(days=REST_TRIGGER_DAYS)
            next_start = rest_started_at + timedelta(days=gap)

            cycle.last_updated_at = last_record_date
            cycle.rest_started_at = rest_started_at
            cycle.closed_at = next_start - timedelta(days=1)
            cycle.save(update_fields=["last_updated_at", "rest_started_at", "closed_at"])

            if skip_ai:
                cycle.analysis = DUMMY_CYCLE_ANALYSIS
                cycle.save(update_fields=["analysis"])
                summary["cycle_analyses"] += 1
            else:
                result = generate_cycle_analysis(user, cycle)
                if result:
                    summary["cycle_analyses"] += 1

            summary["cycles"] += 1
            cursor = next_start

        # 사이클 4: 아직 진행중 (오늘까지 이어짐)
        window_start = cursor
        window_end = max(window_start, today - timedelta(days=random.randint(0, 2)))

        cycle4 = Cycle.objects.create(
            user=user, state=Cycle.State.ACTIVE, count=4, started_at=window_start,
        )
        user.current_cycle = cycle4
        user.save(update_fields=["current_cycle"])

        logs_created, quests_created, quests_done = self._populate_activity(
            user, cycle4, char_state, window_start, window_end, rng, allow_in_progress=True,
        )
        summary["logs"] += logs_created
        summary["quests"] += quests_created
        summary["quests_done"] += quests_done
        summary["cycles"] += 1

        cycle4.last_updated_at = window_end
        cycle4.save(update_fields=["last_updated_at"])

        # 위클리 카드: 전체 기간을 주(월요일 시작) 단위로 훑으면서 실제 배치 함수를 그대로 호출
        week_cursor = start_date - timedelta(days=start_date.weekday())
        while week_cursor <= today:
            if skip_ai:
                created = self._create_dummy_weekly_card(user, week_cursor)
            else:
                created = generate_weekly_analysis(user, week_cursor)
            if created:
                summary["weekly_cards"] += 1
            week_cursor += timedelta(days=7)

        char_state.refresh_from_db()
        summary["total_score"] = char_state.total_score
        return summary

    def _create_dummy_weekly_card(self, user, week_start: date):
        from weekly_card.models import RecommendedQuest, WeeklyAnalysis

        week_end = week_start + timedelta(days=6)
        if WeeklyAnalysis.objects.filter(user=user, week_start=week_start).exists():
            return None

        plus_log_count = PlusLog.objects.filter(
            user=user, created_at__date__gte=week_start, created_at__date__lte=week_end,
        ).count()
        if plus_log_count < 3:
            return None

        success_quest_count = Quest.objects.filter(
            cycle__user=user, state=Quest.State.DONE,
            last_checked__range=(week_start, week_end),
        ).count()

        analysis = WeeklyAnalysis.objects.create(
            user=user, week_start=week_start, week_end=week_end,
            analysis={"weekly_summary": "(더미) 이번 주도 꾸준히 기록을 이어갔어요."},
            rest_NT_content="(더미) 그동안의 기록은 사라지지 않아요. 원할 때 다시 시작해요.",
            plus_log_count=plus_log_count,
            success_quest_count=success_quest_count,
        )
        for content in random.sample(QUEST_BANK, k=min(5, len(QUEST_BANK))):
            RecommendedQuest.objects.create(
                weekly_analysis=analysis, quest_content=content, reason="(더미) 추천 사유",
            )
        WeeklyAnalysis.objects.filter(pk=analysis.pk).update(
            created_at=_aware(min(week_end + timedelta(days=1), date.today()), 9, 0)
        )
        return analysis

    # ------------------------------------------------------------------
    # 한 사이클의 활동 기간(window_start~window_end)에 로그/퀘스트를 채운다.
    # ------------------------------------------------------------------
    def _populate_activity(self, user, cycle, char_state, window_start, window_end, rng, allow_in_progress):
        logs_created = 0
        quests_created = 0
        quests_done = 0

        active_days = (window_end - window_start).days + 1
        day = window_start
        while day <= window_end:
            is_anchor = day == window_start or day == window_end
            if is_anchor or rng.random() < 0.55:
                num_logs = 2 if rng.random() < 0.15 else 1
                for n in range(num_logs):
                    self._create_log(user, cycle, char_state, day, is_first_of_day=(n == 0))
                    logs_created += 1
            day += timedelta(days=1)

        # 퀘스트: 짧은 기간(예: 진행중 사이클 초반)이면 1개, 넉넉하면 2개
        quest_starts = [window_start]
        if active_days >= 8:
            quest_starts.append(window_start + timedelta(days=max(0, active_days - QUEST_DEADLINE_DAYS)))

        for idx, q_start in enumerate(quest_starts):
            is_last_quest = allow_in_progress and idx == len(quest_starts) - 1
            check_days = [q_start, q_start + timedelta(days=2), q_start + timedelta(days=4)]
            check_days = [min(d, window_end) for d in check_days]
            # 같은 날짜가 겹치면(짧은 기간) 하루 뒤로 밀어서 중복 체크를 피한다.
            for k in range(1, len(check_days)):
                if check_days[k] <= check_days[k - 1]:
                    check_days[k] = min(check_days[k - 1] + timedelta(days=1), window_end)

            if is_last_quest:
                # 마지막 사이클의 마지막 퀘스트는 아직 진행중인 상태로 남겨서 "현재 진행중" 느낌을 준다.
                check_days = [d for d in check_days if d <= window_end][:2]

            quest = Quest.objects.create(
                cycle=cycle, state=Quest.State.ACTIVE,
                quest_content=rng.choice(QUEST_BANK), started_at=q_start,
            )
            quests_created += 1

            for check_day in check_days:
                if quest.last_checked == check_day:
                    continue
                self._check_quest(quest, char_state, check_day)

            if quest.state == Quest.State.DONE:
                quests_done += 1

        return logs_created, quests_created, quests_done

    def _create_log(self, user, cycle, char_state, day: date, is_first_of_day: bool):
        content, asset_name = random.choice(LOG_BANK)
        created_at = _aware(day, random.randint(7, 22), random.randint(0, 59))

        log = PlusLog.objects.create(
            user=user, cycle=cycle, content=content, state="DONE",
        )
        asset = Asset.objects.filter(asset_name=asset_name, is_active=True).first()
        PlusLog.objects.filter(pk=log.pk).update(
            created_at=created_at, processed_at=created_at, asset=asset,
        )

        if is_first_of_day:
            char_state.total_score += 1
            char_state.save(update_fields=["total_score"])
            event = CharacterGrowthEvent.objects.create(
                char_state=char_state, source_type=CharacterGrowthEvent.SourceType.LOG,
                score=1, log_id=log.pk,
            )
            CharacterGrowthEvent.objects.filter(pk=event.pk).update(created_at=created_at)

    def _check_quest(self, quest: Quest, char_state: CharacterState, check_day: date):
        if quest.count < 2:
            quest.count += 1
            quest.state = Quest.State.ACTIVE
            score = 2
        else:
            quest.count += 1
            quest.state = Quest.State.DONE
            score = 5

        quest.last_checked = check_day
        quest.save(update_fields=["count", "state", "last_checked"])

        char_state.total_score += score
        char_state.save(update_fields=["total_score"])

        event = CharacterGrowthEvent.objects.create(
            char_state=char_state, source_type=CharacterGrowthEvent.SourceType.QUEST,
            score=score, quest=quest,
        )
        CharacterGrowthEvent.objects.filter(pk=event.pk).update(
            created_at=_aware(check_day, random.randint(9, 21), random.randint(0, 59))
        )
