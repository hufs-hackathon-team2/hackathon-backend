# cycle/management/commands/nightly_rest_check.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from cycle.services import check_and_apply_rest_transition


class Command(BaseCommand):
    help = "매일 밤 ACTIVE 사이클을 순회하며 휴식기 전환 여부를 판정"

    def handle(self, *args, **options):
        today = timezone.localdate()
        users_with_active_cycle = User.objects.filter(current_cycle__state='ACTIVE')

        success_count = 0
        for user in users_with_active_cycle:
            try:
                transitioned = check_and_apply_rest_transition(user, today)
                if transitioned:
                    success_count += 1
            except Exception as e:
                self.stderr.write(f"user {user.pk} 처리 중 에러: {e}")
                # 한 유저 실패가 전체 배치를 막지 않도록 계속 진행

        self.stdout.write(f"완료. {success_count}명 RESTING 전환됨.")