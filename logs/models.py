from django.db import models

class Asset(models.Model):
    asset_id = models.AutoField(primary_key=True)
    asset_name = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'asset'


class PlusLog(models.Model):
    STATE_CHOICES = [
        ('PENDING', 'Pending'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
    ]

    log_id = models.AutoField(primary_key=True)

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)

    content = models.CharField(max_length=200)
    state = models.CharField(max_length=7, choices=STATE_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    cycle = models.ForeignKey('cycle.Cycle', on_delete=models.CASCADE)

    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'plus_log'