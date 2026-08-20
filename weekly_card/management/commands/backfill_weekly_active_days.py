from django.core.management.base import BaseCommand

from weekly_card.models import WeeklyAnalysis
from weekly_card.services import _collect_weekly_stats


class Command(BaseCommand):
    help = "기존 WeeklyAnalysis 레코드의 active_days를 log_dates/quest_dates(성공일) 기준으로 재계산해서 백필합니다."

    def handle(self, *args, **options):
        analyses = WeeklyAnalysis.objects.select_related('user').all()
        total = analyses.count()
        updated = 0

        for analysis in analyses:
            stats = _collect_weekly_stats(analysis.user, analysis.week_start, analysis.week_end)
            new_value = stats["active_days"]
            if analysis.active_days != new_value:
                analysis.active_days = new_value
                analysis.save(update_fields=["active_days"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(f"백필 완료: 전체 {total}건 중 {updated}건 갱신")
        )
