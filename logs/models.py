from django.db import models
from django.utils import timezone

class Asset(models.Model):
    asset_id = models.AutoField(primary_key=True)
    asset_name = models.CharField(max_length=50)
    category = models.CharField(max_length=20)
    image_url = models.URLField(max_length=250)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'Asset'


class PlusLog(models.Model):
    STATE_CHOICES = [
        ('PENDING', 'Pending'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
    ]

    log_id = models.AutoField(primary_key=True)

    user_id = models.IntegerField() # FK로 수정 필요

    content = models.CharField(max_length=200)
    state = models.CharField(max_length=7, choices=STATE_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    cycle_id = models.IntegerField() # FK로 수정 필요

    assets = models.ManyToManyField(Asset, through='PlusLogAsset')

    class Meta:
        db_table = 'PLUS_Log'


class PlusLogAsset(models.Model):
    log = models.ForeignKey(PlusLog, on_delete=models.CASCADE, db_column = 'Log_ID')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, db_column = 'Asset_ID')
    extracted_keyword = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'PLUS_Log_Asset'
        constraints = [
            models.UniqueConstraint(
                fields=['log', 'asset'],
                name='unique_log_asset'
            )
        ]