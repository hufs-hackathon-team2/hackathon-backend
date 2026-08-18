from datetime import date, timedelta

from django.core.management.base import BaseCommand

from weekly_card.services import run_weekly_batch


class Command(BaseCommand):
    help = "주간 위클리 분석 카드를 생성합니다."

    def handle(self, *args, **options):

        today = date.today()

        week_start = today - timedelta(
            days=today.weekday()
        )

        run_weekly_batch(week_start)

        self.stdout.write(
            self.style.SUCCESS(
                f"Weekly analysis batch 완료: {week_start}"
            )
        )