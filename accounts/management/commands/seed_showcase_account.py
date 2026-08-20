# 시연/데모용 "메인" 계정 하나를 만드는 커맨드.
#
# seed_demo_accounts의 계정 생성/3개월치 이력 채우기 로직을 그대로 재사용하되,
# 이메일을 demo@example.com(중복이면 demo@meotsa.com)으로 고정하고,
# 캐릭터 성장 이력을 45점 단위로 잘라서 완성된 캐릭터 2개를 보관함(CharacterArchive)에
# 넣어준다. 그래야 캐릭터 아카이브 화면도 빈 화면이 아니라 실제 데이터로 보임.
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.management.commands.seed_demo_accounts import Command as SeedDemoAccountsCommand
from accounts.models import User
from characters.models import CharacterArchive, CharacterGrowthEvent

STAGE_TOTAL = 45  # 5+6+7+8+9+10, 캐릭터 하나가 4단계 Final에 도달하는 데 필요한 총점
ARCHIVE_NAMES = ["몽이", "콩이"]  # 완성되어 보관함으로 넘어가는 캐릭터 이름들 (순서대로)
CURRENT_NAME = "두부"  # 지금 막 키우기 시작한 현재 캐릭터 이름
SHOWCASE_INDEX = 900  # seed_demo_accounts 내부에서 char_type/닉네임/이름/관심사를 뽑는 데 쓰는 인덱스


class Command(BaseCommand):
    help = "쇼케이스용 데모 계정(기본: demo@example.com)을 만들고 3개월치 이력 + 캐릭터 아카이브까지 채운다."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="demo@example.com")
        parser.add_argument("--fallback-email", default="demo@meotsa.com")
        parser.add_argument(
            "--skip-ai", action="store_true",
            help="실제 OpenAI 호출 없이 더미 텍스트로 채운다 (파이프라인 검증용)",
        )

    def handle(self, *args, **options):
        email = options["email"]
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f"{email} 이미 존재 - {options['fallback_email']}로 대체"))
            email = options["fallback_email"]
        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f"{email} 도 이미 존재합니다. 계정을 정리한 뒤 다시 실행하세요."))
            return

        today = timezone.localdate()
        seed_cmd = SeedDemoAccountsCommand()

        with transaction.atomic():
            user = seed_cmd._create_user(SHOWCASE_INDEX, email, today)
            user.nickname = "데모"
            user.save(update_fields=["nickname"])

        summary = seed_cmd._seed_history(user, today, options["skip_ai"])
        self.stdout.write(self.style.SUCCESS(
            f"{email} 생성 완료 | 사이클 {summary['cycles']}개 (분석 {summary['cycle_analyses']}건) | "
            f"위클리카드 {summary['weekly_cards']}개 | 플러스로그 {summary['logs']}개 | "
            f"퀘스트 {summary['quests']}개 (성공 {summary['quests_done']}) | "
            f"캐릭터 점수 {summary['total_score']}"
        ))

        self._split_into_archive(user)

    # ------------------------------------------------------------------
    # 캐릭터 성장 이력을 45점 단위로 잘라서, 완성된 캐릭터는 보관함으로 넘기고
    # 남은 점수는 "지금 막 키우기 시작한" 현재 캐릭터로 남긴다.
    # ------------------------------------------------------------------
    def _split_into_archive(self, user: User):
        char_state = user.character_state
        events = list(
            CharacterGrowthEvent.objects.filter(char_state=char_state).order_by("created_at", "id")
        )
        original_char_type = char_state.char_type
        segment_start = char_state.created_at
        running = 0
        name_idx = 0

        for event in events:
            running += event.score
            if running >= STAGE_TOTAL and name_idx < len(ARCHIVE_NAMES):
                archive = CharacterArchive.objects.create(
                    user=user,
                    char_type=original_char_type,
                    character_name=ARCHIVE_NAMES[name_idx],
                    started_at=segment_start,
                )
                CharacterArchive.objects.filter(pk=archive.pk).update(completed_at=event.created_at)
                running -= STAGE_TOTAL
                segment_start = event.created_at
                name_idx += 1

        char_state.total_score = running
        char_state.save(update_fields=["total_score"])
        type(char_state).objects.filter(pk=char_state.pk).update(created_at=segment_start)

        user.character_name = CURRENT_NAME
        user.save(update_fields=["character_name"])

        char_state.refresh_from_db()
        stage_name, gauge, max_gauge = char_state.get_stage_and_gauge()
        self.stdout.write(self.style.SUCCESS(
            f"아카이브 {name_idx}개 생성 완료 | 현재 캐릭터 '{CURRENT_NAME}' "
            f"stage={stage_name} gauge={gauge}/{max_gauge}"
        ))
