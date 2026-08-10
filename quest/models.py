from django.db import models

from cycle.models import Cycle


class Quest(models.Model):
    """
    ERD: 퀘스트(Quest)

    - PK: Quest_ID (CHAR(10))
    - State: ACTIVE, DONE, FAILED, ABANDONED 중 하나
    - Quest_Content: 퀘스트 내용
    - Lastchecked: 가장 최근 체크 날짜. 아직 한 번도 체크 안 했으면 NULL
    - Count: 완료 카운트. 0~3 범위 (DB 레벨 CHECK 제약 추가)
    - Cycle_ID: 소속 사이클 FK (비식별 관계 -> PK에 포함되지 않음)
    """

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "진행중"
        DONE = "DONE", "완료"
        FAILED = "FAILED", "실패"
        ABANDONED = "ABANDONED", "포기"

    quest_id = models.CharField(
        max_length=10,
        primary_key=True,
        db_column="Quest_ID",
    )
    state = models.CharField(
        max_length=9,
        choices=State.choices,
        db_column="State",
    )
    quest_content = models.CharField(
        max_length=200,
        db_column="Quest_Content",
    )
    last_checked = models.DateField(
        null=True,
        blank=True,
        db_column="Lastchecked",
    )
    count = models.PositiveSmallIntegerField(
        default=0,
        db_column="Count",
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        db_column="Cycle_ID",
        related_name="quests",
    )

    class Meta:
        db_table = "quest"
        verbose_name = "퀘스트"
        verbose_name_plural = "퀘스트 목록"
        constraints = [
            models.CheckConstraint(
                check=models.Q(count__gte=0) & models.Q(count__lte=3),
                name="quest_count_between_0_and_3",
            ),
        ]

    def __str__(self):
        return f"{self.quest_id} ({self.state})"
