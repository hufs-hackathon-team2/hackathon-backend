# 캐릭터 성장 완료 순간을 촬영하기 위한 전용 데모 계정 생성 커맨드.
#
# 조건:
# - 보관함(CharacterArchive)에 이미 성장 완료한 캐릭터 3개 (다른 이름, 다른 기간;
#   char_type은 cat/dog 2종뿐이라 완전히 다른 동물 3개는 불가능해서 2:1로 섞음)
# - 작심삼일 퀘스트 1개가 진행중, count=2, last_checked=어제
#   -> 오늘 마지막 체크를 누르면 count=3, state=DONE으로 완료됨
# - 그 마지막 체크의 +5점으로 게이지가 정확히 45(4단계 Final)를 채우도록
#   현재 캐릭터의 total_score를 미리 40으로 맞춰둠
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from characters.models import CharacterArchive, CharacterGrowthEvent
from cycle.models import Cycle
from logs.models import Asset, PlusLog
from quest.models import Quest

DEMO_PASSWORD = "Demo1234!"
QUEST_DEADLINE_DAYS = 7  # quest.services.QUEST_DEADLINE_DAYS와 동일

# (이름, char_type, 시작일 오프셋(오늘 기준 -일), 완료일 오프셋)
ARCHIVE_PLAN = [
    ("두부", "DOG", 90, 69),
    ("나비", "CAT", 69, 42),
    ("초코", "DOG", 42, 24),
]
CURRENT_CHAR_TYPE = "cat"
CURRENT_CHAR_NAME = "감자"
SCORE_BEFORE_FINAL_CHECK = 40  # +5(퀘스트 완료) = 45 = 4단계 Final 정확히 채움

# 캐릭터 방의 "최근 활동" 아이콘 캐러셀이 비어 보이지 않도록 채워두는 플러스 로그.
# 각 로그가 실제로 +1점씩 채점되어 SCORE_BEFORE_FINAL_CHECK에 포함된다.
PLUS_LOG_PLAN = [
    ("아침에 20분 조깅했다", "run", 3),
    ("저녁 먹고 동네 산책 30분 다녀옴", "walk", 6),
    ("헬스장 가서 웨이트 1시간", "weights", 10),
    ("집에서 필라테스 20분", "ballet", 14),
    ("점심에 샐러드로 든든하게", "salad", 18),
]


def _aware(d, hour=9, minute=0):
    return timezone.make_aware(datetime.combine(d, time(hour=hour, minute=minute)))


class Command(BaseCommand):
    help = "캐릭터 성장 완료 촬영용 데모 계정을 만든다 (보관함 3개 + 마지막 체크 한 번 남은 퀘스트)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="grow@example.com")

    def handle(self, *args, **options):
        email = options["email"]
        if User.objects.filter(email=email).exists():
            raise CommandError(f"{email} 이 이미 존재합니다. 다른 이메일을 쓰거나 기존 계정을 정리하세요.")

        today = timezone.localdate()

        with transaction.atomic():
            user = User.objects.create_user(
                email=email, password=DEMO_PASSWORD, nickname="성장영상",
            )
            user.onboarding_completed = True
            user.push_permission_granted = True
            user.interest = "캐릭터 키우기"
            user.character_type = CURRENT_CHAR_TYPE
            user.character_name = CURRENT_CHAR_NAME
            user.save()

            earliest_started = today - timedelta(days=ARCHIVE_PLAN[0][2])
            User.objects.filter(pk=user.pk).update(created_at=_aware(earliest_started))

            # 보관함: 이미 완성해서 넘긴 캐릭터 3개
            for name, char_type, start_offset, end_offset in ARCHIVE_PLAN:
                started_at = today - timedelta(days=start_offset)
                completed_at = today - timedelta(days=end_offset)
                archive = CharacterArchive.objects.create(
                    user=user, char_type=char_type, character_name=name,
                    started_at=_aware(started_at),
                )
                CharacterArchive.objects.filter(pk=archive.pk).update(
                    completed_at=_aware(completed_at)
                )

            # 현재 키우고 있는 캐릭터: 마지막 아카이브 완료 시점부터 지금까지 성장 중.
            # PLUS_LOG_PLAN 각각이 실제로 +1점씩 채점되므로, 그만큼을 뺀 값을 베이스로 두고
            # 로그를 만들면서 다시 채워 최종적으로 SCORE_BEFORE_FINAL_CHECK에 도달하게 한다.
            current_growth_start = today - timedelta(days=ARCHIVE_PLAN[-1][3])
            char_state = user.character_state
            char_state.char_type = CURRENT_CHAR_TYPE.upper()
            char_state.total_score = SCORE_BEFORE_FINAL_CHECK - len(PLUS_LOG_PLAN)
            char_state.save(update_fields=["char_type", "total_score"])
            type(char_state).objects.filter(pk=char_state.pk).update(
                created_at=_aware(current_growth_start)
            )

            # 현재 사이클 (퀘스트/플러스로그가 소속될 ACTIVE 사이클)
            cycle = Cycle.objects.create(
                user=user, state=Cycle.State.ACTIVE, count=1,
                started_at=current_growth_start,
            )
            user.current_cycle = cycle
            user.save(update_fields=["current_cycle"])

            # 캐릭터 방 "최근 활동" 아이콘용 플러스 로그 (하루 1개 제한을 지키도록 날짜를 모두 다르게)
            for content, asset_name, days_ago in PLUS_LOG_PLAN:
                log_at = _aware(today - timedelta(days=days_ago), hour=9)
                asset = Asset.objects.filter(asset_name=asset_name, is_active=True).first()
                log_entry = PlusLog.objects.create(
                    user=user, cycle=cycle, content=content, state="DONE", asset=asset,
                )
                PlusLog.objects.filter(pk=log_entry.pk).update(
                    created_at=log_at, processed_at=log_at,
                )
                char_state.total_score += 1
                char_state.save(update_fields=["total_score"])
                event = CharacterGrowthEvent.objects.create(
                    char_state=char_state,
                    source_type=CharacterGrowthEvent.SourceType.LOG,
                    score=1, log=log_entry,
                )
                CharacterGrowthEvent.objects.filter(pk=event.pk).update(created_at=log_at)

            # 작심삼일 퀘스트: 2번 체크 완료(count=2), 마지막 체크가 어제라 오늘 한 번 더
            # 누르면 count=3/DONE으로 완료된다. started_at은 7일 데드라인에 안전하게 여유를 둠.
            quest_started_at = today - timedelta(days=3)
            quest = Quest.objects.create(
                cycle=cycle, state=Quest.State.ACTIVE,
                quest_content="자기 전 스트레칭 10분",
                started_at=quest_started_at,
                count=2,
                last_checked=today - timedelta(days=1),
            )

        deadline = quest.started_at + timedelta(days=QUEST_DEADLINE_DAYS)
        self.stdout.write(self.style.SUCCESS(
            f"{email} 생성 완료 (비밀번호: {DEMO_PASSWORD})\n"
            f"  보관함: {', '.join(f'{n}({t})' for n, t, *_ in ARCHIVE_PLAN)}\n"
            f"  현재 캐릭터: {CURRENT_CHAR_NAME}({CURRENT_CHAR_TYPE}) total_score={SCORE_BEFORE_FINAL_CHECK} "
            f"(마지막 체크 +5 -> 45, 4단계 Final)\n"
            f"  퀘스트: '{quest.quest_content}' count={quest.count} last_checked={quest.last_checked} "
            f"started_at={quest.started_at} (데드라인 {deadline}까지 유효)"
        ))
