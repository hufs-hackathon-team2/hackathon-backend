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
    # default=""는 마이그레이션 백필용. 실제 2~10자 검증은 SignupSerializer가 담당한다.
    nickname = models.CharField(max_length=10, default="")
    onboarding_completed = models.BooleanField(default=False)
    push_permission_granted = models.BooleanField(default=False)
    notification_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # NOTE(ON-01): 기능명세서에 "작성 결과를 저장한다"/"빈칸으로 두면 오류"로 명시됨. 100자 이하 자유 텍스트.
    interest = models.CharField(max_length=100, default="")
    # NOTE(ON-03/CY-01): 김다은 cycle 앱 코드가 이미 user.current_cycle을 getter/setter로 쓰고 있어 추가함(2026-08-16).
    # on_delete=SET_NULL: PROTECT면 AU-06(회원 탈퇴, 하드 삭제+CASCADE)가 ProtectedError로 깨짐.
    current_cycle = models.ForeignKey(
        "cycle.Cycle", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class CharacterType(models.TextChoices):
        CAT = "cat", "고양이"
        DOG = "dog", "강아지"

    # NOTE(ON-02): 캐릭터는 고양이/강아지 2종 고정(카탈로그 아님). 프론트 S12CharacterSelect 스펙에 맞춰 종류+이름으로 구성.
    character_type = models.CharField(
        max_length=3, choices=CharacterType.choices, null=True, blank=True
    )
    character_name = models.CharField(max_length=10, default="")

    USERNAME_FIELD = "email"

    objects = UserManager()

    class Meta:
        constraints = [
            # character_type/character_name는 항상 같이 비어있거나 같이 차 있어야 한다(리뷰 지적, 2026-08-16).
            models.CheckConstraint(
                check=models.Q(character_type__isnull=True, character_name="")
                | (models.Q(character_type__isnull=False) & ~models.Q(character_name="")),
                name="user_character_type_and_name_together",
            ),
        ]


class RefreshToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=200)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=200)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
