import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from .models import PasswordResetToken, RefreshToken, User, UserIdCounter

PASSWORD_RESET_TOKEN_LIFETIME = timedelta(minutes=30)


def generate_user_id():
    with transaction.atomic():
        counter, _ = UserIdCounter.objects.select_for_update().get_or_create(pk=1)
        counter.last_number = F("last_number") + 1
        counter.save()
        counter.refresh_from_db()
        return f"USR{counter.last_number:07d}"


def issue_tokens(user):
    jwt_refresh = JWTRefreshToken.for_user(user)
    access = str(jwt_refresh.access_token)
    refresh = str(jwt_refresh)
    expires_at = timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"]
    RefreshToken.objects.create(user=user, token=refresh, expires_at=expires_at)
    return access, refresh


def signup(email, password, nickname):
    user = User.objects.create_user(email=email, password=password, nickname=nickname)
    access, refresh = issue_tokens(user)
    return user, access, refresh


def create_first_cycle(user):
    # 지연 import: cycle이 accounts.models를 참조하는 순환 관계라 모듈 최상단에서 import하지 않는다.
    from cycle.services import start_cycle_after_onboarding

    start_cycle_after_onboarding(user, timezone.localdate())


def complete_onboarding(user):
    if not user.onboarding_completed:
        # create_first_cycle 실패 시 onboarding_completed도 같이 롤백되어야 한다.
        # 온보딩 완료는 되돌릴 수 없는 전이라, 플래그만 저장되고 사이클 생성이 실패하면
        # 재시도 경로가 없는 채로 영구히 멈추기 때문이다.
        with transaction.atomic():
            user.onboarding_completed = True
            user.save(update_fields=["onboarding_completed"])
            create_first_cycle(user)
    return user


def request_password_reset(email):
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # 이메일 존재 여부를 노출하지 않기 위해 조용히 종료한다.
        return

    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + PASSWORD_RESET_TOKEN_LIFETIME
    PasswordResetToken.objects.create(user=user, token=token, expires_at=expires_at)

    send_mail(
        subject="[헬시 플레져] 비밀번호 재설정",
        message=(
            f"아래 토큰으로 비밀번호를 재설정해주세요. ({PASSWORD_RESET_TOKEN_LIFETIME.seconds // 60}분간 유효)\n\n"
            f"{token}"
        ),
        from_email=None,
        recipient_list=[email],
    )


def confirm_password_reset(db_token, new_password):
    user = db_token.user
    user.set_password(new_password)
    user.save(update_fields=["password"])
    db_token.used_at = timezone.now()
    db_token.save(update_fields=["used_at"])
