from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from .models import PasswordResetToken, RefreshToken, User


def _validate_password_strength(value):
    try:
        validate_password(value)
    except DjangoValidationError as e:
        raise serializers.ValidationError(e.messages)
    return value


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    nickname = serializers.CharField(min_length=2, max_length=10)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value

    def validate_password(self, value):
        return _validate_password_strength(value)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def to_internal_value(self, data):
        # 프론트가 이메일 값을 username 키로 보내는 경우를 위한 별칭 처리.
        # QueryDict(form/multipart)는 {**data, ...}로 펼치면 값이 리스트로 깨지므로
        # 반드시 .copy()로 구조를 보존한 채 수정한다.
        if "email" not in data and "username" in data:
            data = data.copy()
            data["email"] = data["username"]
        return super().to_internal_value(data)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"],
            password=attrs["password"],
        )
        if user is None:
            raise AuthenticationFailed("이메일 또는 비밀번호가 올바르지 않습니다.")
        attrs["user"] = user
        return attrs


class RefreshSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()

    def validate(self, attrs):
        invalid_error = AuthenticationFailed("리프레시 토큰이 유효하지 않습니다.")
        token_str = attrs["refresh_token"]

        try:
            jwt_token = JWTRefreshToken(token_str)
        except TokenError:
            raise invalid_error

        db_token = RefreshToken.objects.select_related("user").filter(
            token=token_str, revoked_at__isnull=True
        ).first()
        if db_token is None or db_token.expires_at <= timezone.now():
            raise invalid_error

        attrs["user"] = db_token.user
        attrs["jwt_token"] = jwt_token
        attrs["db_token"] = db_token
        return attrs


class InterestSerializer(serializers.Serializer):
    interest = serializers.CharField(min_length=1, max_length=100)


class CharacterSelectSerializer(serializers.Serializer):
    character_type = serializers.ChoiceField(choices=User.CharacterType.choices)
    character_name = serializers.CharField(min_length=2, max_length=10)


class NotificationSettingsSerializer(serializers.Serializer):
    restart_notification = serializers.BooleanField(required=False)
    activity_notification = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "restart_notification 또는 activity_notification 중 하나는 필요합니다."
            )
        return attrs


class WithdrawalSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["user"]
        if not user.check_password(value):
            raise AuthenticationFailed("비밀번호가 올바르지 않습니다.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        return _validate_password_strength(value)

    def validate(self, attrs):
        db_token = PasswordResetToken.objects.select_related("user").filter(
            token=attrs["token"], used_at__isnull=True
        ).first()
        if db_token is None or db_token.expires_at <= timezone.now():
            raise serializers.ValidationError(
                {"token": "토큰이 유효하지 않거나 만료되었습니다."}
            )
        attrs["db_token"] = db_token
        return attrs
