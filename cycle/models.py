from django.conf import settings
from django.db import models


class Cycle(models.Model):
    """
    ERD: 사이클(Cycle) - 2026-08-14 캡처 기준

    - PK: Cycle_ID -> Django 기본 정수 PK(id)로 대체
    - User_ID: 아직 User 모델이 없어 FK를 걸지 못하는 상태.
      TODO: User 모델 생성 후 아래 user 필드를
      models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, ...)
      로 교체하고 이 IntegerField는 삭제할 것.
    - State: ACTIVE, RESTING, CLOSED 중 하나
    - Analysis: AI가 사이클 종료 시 생성한 요약 분석 텍스트 (nullable)
    - Count: 해당 사용자의 몇 번째 사이클인지 (C1/C6에서 생성 시 계산해서 채움)
    - Last_Updated_At: 마지막 기록 시각 (C2/C3/C4 가드 조건 판정 기준)
    - Closed_At: 종료일 (C5/C8에서 기록)
    - Rest_Started_At: 휴식 시작일 (C3/C4에서 기록)
    - Notified_At: 휴식기 알림 발송 시각 (C3/C4에서 기록)
    - Started_At: 사이클 시작일 (C1에서 기록)
    - Analysis_Request_Count: AI 분석 요청 횟수, 0~3 (DB 레벨 제약 포함)
    """

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "진행중"
        RESTING = "RESTING", "휴식"
        CLOSED = "CLOSED", "종료"

    # Cycle_ID는 Django에서 기본 생성한 PK(id, 정수)로 대체

    # TODO: User 모델 생성 후 FK로 교체
    # user = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.CASCADE,
    #     db_column="User_ID",
    #     related_name="cycles",  # 역참조를 할 때 사용할 이름 지정
    # )
    user_id_placeholder = models.IntegerField(
        db_column="User_ID",
        help_text="임시 필드. User 모델 생성 후 user FK로 교체 예정",
    )
    state = models.CharField(
        max_length=7,
        choices=State.choices,
        db_column="State",
    )
    analysis = models.TextField(
        null=True,
        blank=True,
        db_column="Analysis",
    )
    count = models.PositiveSmallIntegerField(
        db_column="Count",
    )
    last_updated_at = models.DateField(
        null=True,
        blank=True,
        db_column="Last_Updated_At",
    )
    closed_at = models.DateField(
        null=True,
        blank=True,
        db_column="Closed_At",
    )
    rest_started_at = models.DateField(
        null=True,
        blank=True,
        db_column="Rest_Started_At",
    )
    notified_at = models.DateField(
        null=True,
        blank=True,
        db_column="Notified_At",
    )
    started_at = models.DateField(
        db_column="Started_At",
    )
    analysis_request_count = models.PositiveSmallIntegerField(
        default=0,
        db_column="Analysis_Request_Count",
    )

    class Meta:
        db_table = "cycle"
        verbose_name = "사이클"
        verbose_name_plural = "사이클 목록"
        constraints = [
            models.CheckConstraint(
                check=models.Q(analysis_request_count__gte=0)
                & models.Q(analysis_request_count__lte=3),
                name="cycle_analysis_request_count_between_0_and_3",
            ),
        ]

    def __str__(self):
        return f"{self.id} ({self.state})"
