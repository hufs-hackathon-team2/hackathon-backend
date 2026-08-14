from django.conf import settings
from django.db import models


class Cycle(models.Model):
    """
    ERD: 사이클(Cycle) - 2026-08-14 캡처 기준

    - PK: Cycle_ID -> Django 기본 정수 PK(id)로 대체
    - user: accounts.User 모델과 FK로 연결
    - state: ACTIVE, RESTING, CLOSED 중 하나
    - analysis: AI가 사이클 종료 시 생성한 요약 분석 텍스트 (nullable)
    - count: 해당 사용자의 몇 번째 사이클인지
    - last_updated_at: 마지막 기록 시각 (nullable)
    - closed_at: 종료일 (nullable)
    - rest_started-at: 휴식 시작일 (nullable)
    - notified_at: 휴식기 알림 발송 시각 (nullable)
    - started_at: 사이클 시작일
    - analysis_request_count: AI 분석 요청 횟수, 0~3 (DB 레벨 제약 포함)
    """

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "진행중"
        RESTING = "RESTING", "휴식"
        CLOSED = "CLOSED", "종료"

    # Cycle_ID는 Django에서 기본 생성한 PK(id, 정수)로 대체

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name="cycles",
    )

    state = models.CharField(
        max_length=7,
        choices=State.choices,
    )

    analysis = models.JSONField(
        null=True,
        blank=True,
    )

    count = models.PositiveSmallIntegerField(
        default=1,
    )

    last_updated_at = models.DateField(
        null=True,
        blank=True,
    )

    closed_at = models.DateField(
        null=True,
        blank=True,
    )
    rest_started_at = models.DateField(
        null=True,
        blank=True,
    )
    notified_at = models.DateField(
        null=True,
        blank=True,
    )

    started_at = models.DateField(
    )

    analysis_request_count = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        db_table = "cycle"
        verbose_name = "사이클"
        verbose_name_plural = "사이클 목록"
        ordering = ['-started_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(analysis_request_count__gte=0)
                & models.Q(analysis_request_count__lte=3),
                name="cycle_analysis_request_count_between_0_and_3",
            ),
        ]

    def __str__(self):
        return f"{self.id} ({self.state})"
