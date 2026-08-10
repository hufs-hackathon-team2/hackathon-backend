from django.conf import settings
from django.db import models


class Cycle(models.Model):
    """
    ERD: 사이클(Cycle)

    - PK: Cycle_ID (CHAR(10))
    - User_ID: 사용자 참조 FK (관계선이 ERD 캡처에 없어 settings.AUTH_USER_MODEL로 가정,
      실제 User 모델이 따로 있다면 이 부분만 교체하시면 됩니다)
    - State: ACTIVE, RESTING, CLOSED 중 하나
    - Analysis: AI가 생성한 사이클 분석 텍스트 (nullable)
    """

    class State(models.TextChoices):
        ACTIVE = "ACTIVE", "진행중"
        RESTING = "RESTING", "휴식"
        CLOSED = "CLOSED", "종료"

    '''cycle_ID는 장고에서 기본 생성한 PK로 대체
    '''
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="User_ID",
        related_name="cycles", #역참조를 할 때 사용할 이름 지정
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

    class Meta:
        db_table = "cycle"
        verbose_name = "사이클"
        verbose_name_plural = "사이클 목록"

    def __str__(self):
        return f"{self.id} ({self.state})"
