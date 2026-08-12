from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserIdCounter(models.Model):
    last_number = models.PositiveIntegerField(default=0)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다.")

        # models.py가 로드되는 시점에 services.py를 임포트하면 순환 임포트가 발생해 여기서 지연 임포트한다.
        from .services import generate_user_id

        email = self.normalize_email(email)
        user = self.model(user_id=generate_user_id(), email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    user_id = models.CharField(max_length=10, primary_key=True)
    email = models.EmailField(max_length=100, unique=True)
    onboarding_completed = models.BooleanField(default=False)
    push_permission_granted = models.BooleanField(default=False)
    notification_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # TODO: current_cycle FK (CY-01 이후 추가)

    USERNAME_FIELD = "email"

    objects = UserManager()


class RefreshToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=200)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
