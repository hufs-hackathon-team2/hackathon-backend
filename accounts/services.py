from django.db import transaction
from django.db.models import F

from .models import UserIdCounter


def generate_user_id():
    with transaction.atomic():
        counter, _ = UserIdCounter.objects.select_for_update().get_or_create(pk=1)
        counter.last_number = F("last_number") + 1
        counter.save()
        counter.refresh_from_db()
        return f"USR{counter.last_number:07d}"
