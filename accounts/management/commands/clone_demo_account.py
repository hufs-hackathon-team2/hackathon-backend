# 이미 만들어진 데모 계정 하나(--source)의 내용을 다른 여러 데모 계정(--targets)에
# 완전히 동일하게 복제한다. seed_demo_accounts는 계정마다 로그/퀘스트 내용과 AI 분석
# 텍스트가 랜덤/개별 생성이라 서로 다른데, 이 커맨드는 촬영 중 계정을 바꿔도 화면
# 내용이 똑같이 보이도록 소스 계정의 모든 행(사이클/로그/퀘스트/위클리카드/캐릭터
# 성장 이벤트)을 그대로 복사한다.
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from characters.models import CharacterGrowthEvent
from cycle.models import Cycle
from logs.models import PlusLog
from quest.models import Quest
from weekly_card.models import RecommendedQuest, WeeklyAnalysis

DEMO_PASSWORD = "Demo1234!"


class Command(BaseCommand):
    help = "소스 데모 계정의 사이클/로그/퀘스트/위클리카드/캐릭터 성장 이력을 다른 데모 계정들에 완전히 동일하게 복제한다."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="복제할 원본 계정 이메일 (예: demo11@example.com)")
        parser.add_argument(
            "--targets", required=True,
            help="쉼표로 구분한 대상 이메일 목록 (예: demo12@example.com,demo13@example.com)",
        )

    def handle(self, *args, **options):
        source_email = options["source"]
        target_emails = [e.strip() for e in options["targets"].split(",") if e.strip()]

        try:
            source_user = User.objects.get(email=source_email)
        except User.DoesNotExist:
            raise CommandError(f"소스 계정 {source_email} 이 존재하지 않습니다.")

        for target_email in target_emails:
            if User.objects.filter(email=target_email).exists():
                self.stdout.write(self.style.WARNING(f"{target_email} 이미 존재 - 스킵"))
                continue
            with transaction.atomic():
                self._clone(source_user, target_email)
            self.stdout.write(self.style.SUCCESS(f"{source_email} -> {target_email} 복제 완료"))

    def _clone(self, source_user: User, target_email: str):
        new_user = User.objects.create_user(
            email=target_email,
            password=DEMO_PASSWORD,
            nickname=source_user.nickname,
        )
        new_user.onboarding_completed = source_user.onboarding_completed
        new_user.push_permission_granted = source_user.push_permission_granted
        new_user.restart_notification = source_user.restart_notification
        new_user.activity_notification = source_user.activity_notification
        new_user.interest = source_user.interest
        new_user.character_type = source_user.character_type
        new_user.character_name = source_user.character_name
        new_user.save()
        User.objects.filter(pk=new_user.pk).update(created_at=source_user.created_at)

        source_char_state = source_user.character_state
        new_char_state = new_user.character_state
        new_char_state.char_type = source_char_state.char_type
        new_char_state.total_score = source_char_state.total_score
        new_char_state.save()
        type(new_char_state).objects.filter(pk=new_char_state.pk).update(
            created_at=source_char_state.created_at
        )

        cycle_map = {}
        for src_cycle in Cycle.objects.filter(user=source_user).order_by("id"):
            new_cycle = Cycle.objects.create(
                user=new_user,
                state=src_cycle.state,
                analysis=src_cycle.analysis,
                count=src_cycle.count,
                last_updated_at=src_cycle.last_updated_at,
                closed_at=src_cycle.closed_at,
                rest_started_at=src_cycle.rest_started_at,
                notified_at=src_cycle.notified_at,
                started_at=src_cycle.started_at,
                analysis_request_count=src_cycle.analysis_request_count,
            )
            cycle_map[src_cycle.id] = new_cycle

        log_map = {}
        for src_log in PlusLog.objects.filter(user=source_user).order_by("log_id"):
            new_log = PlusLog.objects.create(
                user=new_user,
                cycle=cycle_map[src_log.cycle_id],
                content=src_log.content,
                state=src_log.state,
                asset=src_log.asset,
            )
            PlusLog.objects.filter(pk=new_log.pk).update(
                created_at=src_log.created_at,
                processed_at=src_log.processed_at,
                deleted_at=src_log.deleted_at,
            )
            log_map[src_log.log_id] = new_log

        quest_map = {}
        for src_quest in Quest.objects.filter(cycle__user=source_user).order_by("id"):
            new_quest = Quest.objects.create(
                cycle=cycle_map[src_quest.cycle_id],
                state=src_quest.state,
                quest_content=src_quest.quest_content,
                last_checked=src_quest.last_checked,
                abandoned_at=src_quest.abandoned_at,
                count=src_quest.count,
                started_at=src_quest.started_at,
            )
            quest_map[src_quest.id] = new_quest

        for src_event in CharacterGrowthEvent.objects.filter(
            char_state=source_char_state
        ).order_by("id"):
            new_event = CharacterGrowthEvent.objects.create(
                char_state=new_char_state,
                source_type=src_event.source_type,
                score=src_event.score,
                log=log_map.get(src_event.log_id),
                quest=quest_map.get(src_event.quest_id),
            )
            CharacterGrowthEvent.objects.filter(pk=new_event.pk).update(
                created_at=src_event.created_at
            )

        for src_wa in WeeklyAnalysis.objects.filter(user=source_user).order_by("id"):
            new_wa = WeeklyAnalysis.objects.create(
                user=new_user,
                week_start=src_wa.week_start,
                week_end=src_wa.week_end,
                plus_log_count=src_wa.plus_log_count,
                success_quest_count=src_wa.success_quest_count,
                rest_NT_content=src_wa.rest_NT_content,
                analysis=src_wa.analysis,
            )
            WeeklyAnalysis.objects.filter(pk=new_wa.pk).update(created_at=src_wa.created_at)
            for src_rq in src_wa.recommendations.all().order_by("id"):
                RecommendedQuest.objects.create(
                    weekly_analysis=new_wa,
                    quest_content=src_rq.quest_content,
                    reason=src_rq.reason,
                )

        if source_user.current_cycle_id:
            new_user.current_cycle = cycle_map[source_user.current_cycle_id]
            new_user.save(update_fields=["current_cycle"])
