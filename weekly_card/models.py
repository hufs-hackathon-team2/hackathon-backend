from django.db import models

from cycle.models import Cycle  # noqa: F401  (참고용, 직접 참조는 안 함)


class WeeklyAnalysis(models.Model):
    """
    주 1회 배치가 생성하는 "위클리 카드" 집계 결과.

    - GET /weekly-card 응답의 원본 데이터
    - GET /quests/recommended 응답도 이 테이블(정확히는 자식 테이블 RecommendedQuest)을 공유해서 조회함
    - User_ID: 아직 User 모델이 없어 FK를 걸지 못하는 상태.
      TODO: User 모델 생성 후 user 필드를 FK로 교체할 것.
    """

    # TODO: User 모델 생성 후 FK로 교체
    # user = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.CASCADE,
    #     db_column="User_ID",
    #     related_name="weekly_analyses",
    # )
    user_id_placeholder = models.IntegerField(
        db_column="User_ID",
        help_text="임시 필드. User 모델 생성 후 user FK로 교체 예정",
    )
    week_start = models.DateField(
        db_column="Week_Start",
    )
    week_end = models.DateField(
        db_column="Week_End",
    )
    plus_log_count = models.PositiveSmallIntegerField(
        default=0,
        db_column="Plus_Log_Count",
    )
    success_quest_count = models.PositiveSmallIntegerField(
        default=0,
        db_column="Success_Quest_Count",
    )
    active_days = models.PositiveSmallIntegerField(
        default=0,
        db_column="Active_Days",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="Created_At",
    )
    rest_NT_content = models.CharField(
        max_length=200,
        db_column="Rest_NT_Content",
        blank=True
    )
    analysis = models.TextField(
        blank=True, #Django Admin이나 폼에서 이 필드를 입력 안 하고 저장해도 "필수 항목입니다" 에러가 안 뜨게 허용
        db_column="Analysis",
    )

    class Meta:
        db_table = "weekly_analysis"
        verbose_name = "위클리 분석"
        verbose_name_plural = "위클리 분석 목록"
        constraints = [
            # 같은 유저가 같은 주에 배치 결과를 중복 생성하지 못하도록 방지
            models.UniqueConstraint(
                fields=["user_id_placeholder", "week_start"],
                name="weekly_analysis_unique_user_week",
            ),
        ]

    def __str__(self):
        return f"WeeklyAnalysis({self.id}, {self.week_start}~{self.week_end})"


class RecommendedQuest(models.Model):
    """
    위클리 분석 배치가 함께 생성하는 추천 퀘스트 항목.

    - GET /quests/recommended 는 quest_content만 사용
    - GET /weekly-card 는 quest_content + reason 함께 사용
    """

    weekly_analysis = models.ForeignKey(
        WeeklyAnalysis,
        on_delete=models.CASCADE,
        db_column="Weekly_Analysis_ID",
        related_name="recommendations",
    )
    quest_content = models.CharField(
        max_length=200,
        db_column="Quest_Content",
    )
    reason = models.CharField(
        max_length=200,
        blank=True,
        db_column="Reason",
    )

    class Meta:
        db_table = "recommended_quest"
        verbose_name = "추천 퀘스트"
        verbose_name_plural = "추천 퀘스트 목록"

    def __str__(self):
        return f"RecommendedQuest({self.id}, {self.quest_content})"
