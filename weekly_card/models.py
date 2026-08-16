from django.db import models


class WeeklyAnalysis(models.Model):
    """
    주 1회 배치가 생성하는 "위클리 카드" 집계 결과.

    - GET /weekly-card 응답의 원본 데이터
    - GET /quests/recommended 응답도 이 테이블(정확히는 자식 테이블 RecommendedQuest)을
      공유해서 조회함
    - rest_NT_content: 휴식기 알림(notification) 발송 문구

    db_column은 지정하지 않음 -> Django 기본 규칙(필드명 그대로, 소문자)을 컬럼명으로 사용.
    """

    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name="weekly_analysis",
    )
    week_start = models.DateField()
    week_end = models.DateField()
    plus_log_count = models.PositiveSmallIntegerField(default=0)
    success_quest_count = models.PositiveSmallIntegerField(default=0)
    active_days = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    rest_NT_content = models.CharField(
        max_length=200,
        blank=True,
        help_text="휴식기 알림 발송 문구",
    )
    analysis = models.JSONField(
        default=dict,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "weekly_analysis"
        verbose_name = "위클리 분석"
        verbose_name_plural = "위클리 분석 목록"
        ordering = ["-week_start"]
        constraints = [
            # 같은 유저가 같은 주에 배치 결과를 중복 생성하지 못하도록 방지
            models.UniqueConstraint(
                fields=["user", "week_start"],
                name="weekly_analysis_unique_user_week",
            ),
        ]

    def __str__(self):
        return f"WeeklyAnalysis({self.id}, {self.week_start}~{self.week_end})"


class RecommendedQuest(models.Model):
    """
    위클리 분석 배치가 함께 생성하는 추천 퀘스트 항목.
    """

    weekly_analysis = models.ForeignKey(
        WeeklyAnalysis,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    quest_content = models.CharField(max_length=200)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "recommended_quest"
        verbose_name = "추천 퀘스트"
        verbose_name_plural = "추천 퀘스트 목록"

    def __str__(self):
        return f"RecommendedQuest({self.id}, {self.quest_content})"
