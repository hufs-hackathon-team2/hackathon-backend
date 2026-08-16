from django.db import models
from django.conf import settings

from django.db.models.signals import post_save
from django.dispatch import receiver

class CharacterState(models.Model):
    class CharType(models.TextChoices):
        CAT = 'CAT', '고양이'
        DOG = 'DOG', '강아지'

    class Stage(models.TextChoices):
        STAGE_1_SMALL = '1-small', '1단계 Small'
        STAGE_1_BIG = '1-big', '1단계 Big'
        STAGE_2_SMALL = '2-small', '2단계 Small'
        STAGE_2_BIG = '2-big', '2단계 Big'
        STAGE_3_SMALL = '3-small', '3단계 Small'
        STAGE_3_BIG = '3-big', '3단계 Big'
        STAGE_4_FINAL = '4-final', '4단계 Final'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='character_state')
    char_type = models.CharField(max_length=10, choices=CharType.choices, default=CharType.CAT)
    total_score = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'character_state'

    def __str__(self):
        return f"{self.user.email} - {self.current_stage} ({self.total_score}점)"

    def get_stage_and_gauge(self):
        stages = [
            (self.Stage.STAGE_1_SMALL.value, 5),
            (self.Stage.STAGE_1_BIG.value, 6),
            (self.Stage.STAGE_2_SMALL.value, 7),
            (self.Stage.STAGE_2_BIG.value, 8),
            (self.Stage.STAGE_3_SMALL.value, 9),
            (self.Stage.STAGE_3_BIG.value, 10),
        ]

        current_gauge = self.total_score

        for stage_name, max_point in stages:
            if current_gauge < max_point:
                return stage_name, current_gauge, max_point
            current_gauge -= max_point

        return self.Stage.STAGE_4_FINAL.value, 0, 0

    @property
    def current_stage(self):
        stage_name, _, _ = self.get_stage_and_gauge()
        return stage_name


class CharacterGrowthEvent(models.Model):
    class SourceType(models.TextChoices):
        LOG = 'LOG', '플러스 로그'
        QUEST = 'QUEST', '퀘스트'

    char_state = models.ForeignKey(CharacterState, on_delete=models.CASCADE, related_name='growth_events')
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    score = models.PositiveIntegerField()

    log = models.ForeignKey('logs.PlusLog', on_delete=models.SET_NULL, null=True, blank=True)
    quest = models.ForeignKey('quest.Quest', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'character_growth_event'
        constraints = [
            models.CheckConstraint(
                check=(
                    (models.Q(source_type='LOG') & models.Q(log__isnull=False) & models.Q(quest__isnull=True)) |
                    (models.Q(source_type='QUEST') & models.Q(quest__isnull=False) & models.Q(log__isnull=True))
                ),
                name='char_growth_event_exclusive_fk'
            )
        ]

    def __str__(self):
        return f"{self.char_state.user.email} | {self.source_type} | +{self.score}점"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_character_state(sender, instance, created, **kwargs):
    if created:
        CharacterState.objects.create(
            user=instance,
            char_type=CharacterState.CharType.CAT.value,
            total_score=0
        )