from django.db import models

from cycle.models import Cycle


class Quest(models.Model):
    """
    ERD: 퀘스트(Quest) - 2026-08-12 캡처 기준

    - PK: Quest_ID -> Django 기본 정수 PK(id)로 대체
    - state: ACTIVE, DONE, FAILED, ABANDONED 중 하나
    - quest_Content: 퀘스트 내용 (필수, 최대 200자)
    - lastchecked: 가장 최근 체크 날짜. 아직 한 번도 체크 안 했으면 NULL
    - count: 완료 카운트. 0~3 범위 (DB 레벨 CHECK 제약)
    - cycle: 소속 사이클 FK (비식별 관계 -> PK에 포함되지 않음)
    - started_at: 퀘스트 시작일 (Q1에서 기록, D-day/Q5 FAILED 판정 기준)

    User 필드는 두지 않음: Quest -> Cycle -> User로 이미 접근 가능해서
    (Cycle에 이미 user FK가 있음), Quest에 user를 또 두면 같은 정보가
    두 군데 중복 저장되는 정규화 위반이 됨. 소유권 확인은
    Quest.objects.filter(cycle__user=request.user) 형태로 처리할 것.

    db_column은 지정하지 않음 -> Django 기본 규칙(필드명 그대로, 소문자)을 컬럼명으로 사용.
    """

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "진행중"
        DONE = "DONE", "완료"
        FAILED = "FAILED", "실패"
        ABANDONED = "ABANDONED", "포기"

    # Quest_ID는 Django에서 기본 생성한 PK(id, 정수)로 대체

    state = models.CharField(
        max_length=9,
        choices=State.choices,
    )
    quest_content = models.CharField(
        max_length=200,
        blank=False
    )
    last_checked = models.DateField(
        null=True,
        blank=True,
    )
    abandoned_at = models.DateField(
        null=True,
        blank=True,
    )
    count = models.PositiveSmallIntegerField(
        default=0,
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name="quests",
    )
    started_at = models.DateField()

    class Meta:
        db_table = "quest"
        verbose_name = "퀘스트"
        verbose_name_plural = "퀘스트 목록"
        ordering = ["-started_at"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(count__gte=0) & models.Q(count__lte=3),
                name="quest_count_between_0_and_3",
            ),
        ]

    def __str__(self):
        return f"({self.id}-{self.quest_content}-{self.state})"