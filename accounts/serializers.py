from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from .models import RefreshToken, User


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    nickname = serializers.CharField(min_length=2, max_length=10)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

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

        db_token = RefreshToken.objects.filter(
            token=token_str, revoked_at__isnull=True
        ).first()
        if db_token is None or db_token.expires_at <= timezone.now():
            raise invalid_error

        user_id = jwt_token[settings.SIMPLE_JWT["USER_ID_CLAIM"]]
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise invalid_error

        attrs["user"] = user
        attrs["jwt_token"] = jwt_token
        attrs["db_token"] = db_token
        return attrs


class CharacterSelectSerializer(serializers.Serializer):
    # NOTE(ON-02): Character(CH) 앱 확정 전까지 존재 여부 검증 없이 양수 ID만 받는다.
    character_id = serializers.IntegerField(min_value=1)


class NotificationSettingsSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()


class WithdrawalSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        user = self.context["user"]
        if not user.check_password(value):
            raise AuthenticationFailed("비밀번호가 올바르지 않습니다.")
        return value
