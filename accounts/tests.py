from datetime import date, timedelta
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from cycle.models import Cycle

from .models import PasswordResetToken, RefreshToken, User
from .services import generate_user_id


class GenerateUserIdTests(TestCase):
    def test_first_call_returns_usr0000001(self):
        self.assertEqual(generate_user_id(), "USR0000001")

    def test_sequential_increment(self):
        generate_user_id()
        self.assertEqual(generate_user_id(), "USR0000002")


class UserManagerTests(TestCase):
    def test_create_user_sets_expected_defaults(self):
        user = User.objects.create_user(email="test@example.com", password="pw12345!")

        self.assertEqual(user.user_id, "USR0000001")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("pw12345!"))
        self.assertFalse(user.onboarding_completed)
        self.assertFalse(user.push_permission_granted)
        self.assertTrue(user.notification_enabled)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pw12345!")

    def test_duplicate_email_raises_integrity_error(self):
        User.objects.create_user(email="dup@example.com", password="pw12345!")
        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="dup@example.com", password="pw12345!")

    def test_character_type_without_name_raises_integrity_error(self):
        user = User.objects.create_user(email="charonly@example.com", password="pw12345!")
        user.character_type = User.CharacterType.CAT

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                user.save(update_fields=["character_type"])

    def test_current_cycle_defaults_to_none(self):
        user = User.objects.create_user(email="cycle@example.com", password="pw12345!")

        self.assertIsNone(user.current_cycle)

    def test_current_cycle_set_null_when_cycle_deleted(self):
        user = User.objects.create_user(email="cycle2@example.com", password="pw12345!")
        cycle = Cycle.objects.create(user=user, state=Cycle.State.ACTIVE, started_at=date.today())
        user.current_cycle = cycle
        user.save(update_fields=["current_cycle"])

        cycle.delete()
        user.refresh_from_db()

        self.assertIsNone(user.current_cycle)


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/signup/"

    def test_signup_creates_user_and_returns_tokens(self):
        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "correct-horse-battery1",
                "nickname": "말순이",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertEqual(response.data["nickname"], "말순이")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("password", response.data)

        user = User.objects.get(email="new@example.com")
        self.assertEqual(response.data["user_id"], user.user_id)
        self.assertEqual(user.nickname, "말순이")
        self.assertEqual(RefreshToken.objects.filter(user=user).count(), 1)
        self.assertEqual(RefreshToken.objects.get(user=user).token, response.data["refresh"])

    def test_signup_duplicate_email_returns_400(self):
        User.objects.create_user(email="dup@example.com", password="correct-horse-battery1")

        response = self.client.post(
            self.url,
            {
                "email": "dup@example.com",
                "password": "correct-horse-battery1",
                "nickname": "말순이",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_signup_weak_password_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "1234", "nickname": "말순이"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_signup_password_without_digit_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "abcdefgh", "nickname": "말순이"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_signup_password_without_letter_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "12345678", "nickname": "말순이"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_signup_without_nickname_returns_400(self):
        response = self.client.post(
            self.url, {"email": "new@example.com", "password": "correct-horse-battery1"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nickname", response.data)

    def test_signup_nickname_too_short_returns_400(self):
        response = self.client.post(
            self.url,
            {"email": "new@example.com", "password": "correct-horse-battery1", "nickname": "말"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nickname", response.data)

    def test_signup_nickname_too_long_returns_400(self):
        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "correct-horse-battery1",
                "nickname": "가" * 11,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("nickname", response.data)


class LoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/login/"
        self.user = User.objects.create_user(
            email="login@example.com", password="correct-horse-battery"
        )

    def test_login_returns_tokens_and_onboarding_status(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "correct-horse-battery"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_id"], self.user.user_id)
        self.assertEqual(response.data["onboarding_completed"], False)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(
            RefreshToken.objects.filter(user=self.user, token=response.data["refresh"]).count(),
            1,
        )

    def test_login_reflects_onboarding_completed_true(self):
        self.user.onboarding_completed = True
        self.user.save()

        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "correct-horse-battery"}
        )

        self.assertEqual(response.data["onboarding_completed"], True)

    def test_login_wrong_password_returns_401(self):
        response = self.client.post(
            self.url, {"email": "login@example.com", "password": "wrong-password"}
        )

        self.assertEqual(response.status_code, 401)

    def test_login_nonexistent_email_returns_401_with_same_message(self):
        wrong_password_response = self.client.post(
            self.url, {"email": "login@example.com", "password": "wrong-password"}
        )
        nonexistent_email_response = self.client.post(
            self.url, {"email": "nobody@example.com", "password": "wrong-password"}
        )

        self.assertEqual(nonexistent_email_response.status_code, 401)
        self.assertEqual(
            nonexistent_email_response.data["detail"], wrong_password_response.data["detail"]
        )


class RefreshViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/refresh/"
        self.user = User.objects.create_user(
            email="refresh@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "refresh@example.com", "password": "correct-horse-battery"},
        )
        self.refresh_token = login_response.data["refresh"]

    def test_refresh_returns_new_access_token(self):
        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["onboarding_completed"], False)
        self.assertNotIn("refresh", response.data)

    def test_refresh_with_garbage_token_returns_401(self):
        response = self.client.post(self.url, {"refresh_token": "not-a-real-token"})

        self.assertEqual(response.status_code, 401)

    def test_refresh_with_revoked_token_returns_401(self):
        RefreshToken.objects.filter(token=self.refresh_token).update(
            revoked_at=timezone.now()
        )

        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 401)

    def test_refresh_with_expired_db_row_returns_401(self):
        RefreshToken.objects.filter(token=self.refresh_token).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 401)

    def test_refresh_reflects_onboarding_completed_true(self):
        self.user.onboarding_completed = True
        self.user.save()

        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["onboarding_completed"], True)


class LogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/logout/"
        self.user = User.objects.create_user(
            email="logout@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "logout@example.com", "password": "correct-horse-battery"},
        )
        self.refresh_token = login_response.data["refresh"]

    def test_logout_revokes_token_and_returns_204(self):
        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 204)
        db_token = RefreshToken.objects.get(token=self.refresh_token)
        self.assertIsNotNone(db_token.revoked_at)

    def test_logout_with_garbage_token_returns_401(self):
        response = self.client.post(self.url, {"refresh_token": "not-a-real-token"})

        self.assertEqual(response.status_code, 401)

    def test_logout_twice_returns_401_second_time(self):
        self.client.post(self.url, {"refresh_token": self.refresh_token})

        response = self.client.post(self.url, {"refresh_token": self.refresh_token})

        self.assertEqual(response.status_code, 401)

    def test_logout_does_not_revoke_other_sessions(self):
        second_login_response = self.client.post(
            "/auth/login/",
            {"email": "logout@example.com", "password": "correct-horse-battery"},
        )
        second_refresh_token = second_login_response.data["refresh"]

        self.client.post(self.url, {"refresh_token": self.refresh_token})

        refresh_response = self.client.post(
            "/auth/refresh/", {"refresh_token": second_refresh_token}
        )
        self.assertEqual(refresh_response.status_code, 200)


class InterestViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/users/me/interest/"
        self.user = User.objects.create_user(
            email="interest@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "interest@example.com", "password": "correct-horse-battery"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_select_interest_updates_user(self):
        response = self.client.patch(
            self.url, {"interest": "늦은 시간 식사"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["interest"], "늦은 시간 식사")
        self.user.refresh_from_db()
        self.assertEqual(self.user.interest, "늦은 시간 식사")

    def test_select_interest_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.patch(self.url, {"interest": "늦은 시간 식사"}, format="json")

        self.assertEqual(response.status_code, 401)

    def test_select_interest_empty_returns_400(self):
        response = self.client.patch(self.url, {"interest": ""}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("interest", response.data)

    def test_select_interest_too_long_returns_400(self):
        response = self.client.patch(self.url, {"interest": "가" * 101}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("interest", response.data)


class CharacterSelectViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/users/me/character/"
        self.user = User.objects.create_user(
            email="character@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "character@example.com", "password": "correct-horse-battery"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_select_character_updates_user(self):
        response = self.client.patch(
            self.url,
            {"character_type": "cat", "character_name": "나비"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["character_type"], "cat")
        self.assertEqual(response.data["character_name"], "나비")
        self.user.refresh_from_db()
        self.assertEqual(self.user.character_type, "cat")
        self.assertEqual(self.user.character_name, "나비")

    def test_select_character_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.patch(
            self.url,
            {"character_type": "cat", "character_name": "나비"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_select_character_invalid_type_returns_400(self):
        response = self.client.patch(
            self.url,
            {"character_type": "rabbit", "character_name": "나비"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("character_type", response.data)

    def test_select_character_name_too_short_returns_400(self):
        response = self.client.patch(
            self.url,
            {"character_type": "cat", "character_name": "나"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("character_name", response.data)

    def test_select_character_name_too_long_returns_400(self):
        response = self.client.patch(
            self.url,
            {"character_type": "cat", "character_name": "가" * 11},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("character_name", response.data)


class OnboardingCompleteViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/users/me/onboarding-complete/"
        self.user = User.objects.create_user(
            email="onboard@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "onboard@example.com", "password": "correct-horse-battery"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_onboarding_complete_sets_flag_and_calls_create_first_cycle(self):
        with patch("accounts.services.create_first_cycle") as mock_create_cycle:
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["onboarding_completed"], True)
        self.user.refresh_from_db()
        self.assertTrue(self.user.onboarding_completed)
        mock_create_cycle.assert_called_once_with(self.user)

    def test_onboarding_complete_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 401)

    def test_onboarding_complete_is_idempotent(self):
        with patch("accounts.services.create_first_cycle") as mock_create_cycle:
            self.client.post(self.url)
            response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["onboarding_completed"], True)
        mock_create_cycle.assert_called_once()


class SettingsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/settings/"
        self.user = User.objects.create_user(
            email="settings@example.com",
            password="correct-horse-battery1",
            nickname="말순이",
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "settings@example.com", "password": "correct-horse-battery1"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_get_settings_returns_account_info(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["nickname"], "말순이")
        self.assertEqual(response.data["email"], "settings@example.com")

    def test_get_settings_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)


class NotificationSettingsViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/settings/notifications/"
        self.user = User.objects.create_user(
            email="notif-settings@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "notif-settings@example.com", "password": "correct-horse-battery"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_disable_notifications_updates_user(self):
        response = self.client.patch(self.url, {"enabled": False}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification_enabled"], False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.notification_enabled)

    def test_enable_notifications_updates_user(self):
        self.user.notification_enabled = False
        self.user.save()

        response = self.client.patch(self.url, {"enabled": True}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["notification_enabled"], True)

    def test_notification_settings_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.patch(self.url, {"enabled": False}, format="json")

        self.assertEqual(response.status_code, 401)


class WithdrawalViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/users/me/"
        self.user = User.objects.create_user(
            email="withdraw@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "withdraw@example.com", "password": "correct-horse-battery"},
        )
        self.refresh_token = login_response.data["refresh"]
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_withdrawal_deletes_user_and_returns_204(self):
        response = self.client.delete(
            self.url, {"password": "correct-horse-battery"}, format="json"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(User.objects.filter(email="withdraw@example.com").exists())

    def test_withdrawal_cascades_refresh_tokens(self):
        self.assertEqual(RefreshToken.objects.filter(token=self.refresh_token).count(), 1)

        self.client.delete(self.url, {"password": "correct-horse-battery"}, format="json")

        self.assertEqual(RefreshToken.objects.filter(token=self.refresh_token).count(), 0)

    def test_withdrawal_wrong_password_returns_401(self):
        response = self.client.delete(
            self.url, {"password": "wrong-password"}, format="json"
        )

        self.assertEqual(response.status_code, 401)
        self.assertTrue(User.objects.filter(email="withdraw@example.com").exists())

    def test_withdrawal_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.delete(
            self.url, {"password": "correct-horse-battery"}, format="json"
        )

        self.assertEqual(response.status_code, 401)


class PasswordResetRequestViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/password-reset/"
        self.user = User.objects.create_user(
            email="reset@example.com", password="correct-horse-battery"
        )

    def test_existing_email_sends_mail_and_returns_200(self):
        response = self.client.post(self.url, {"email": "reset@example.com"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reset@example.com"])
        self.assertEqual(PasswordResetToken.objects.filter(user=self.user).count(), 1)

    def test_nonexistent_email_returns_200_without_sending(self):
        response = self.client.post(
            self.url, {"email": "nobody@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class PasswordResetConfirmViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/password-reset/confirm/"
        self.user = User.objects.create_user(
            email="confirm@example.com", password="correct-horse-battery"
        )
        self.reset_token = PasswordResetToken.objects.create(
            user=self.user,
            token="valid-token",
            expires_at=timezone.now() + timedelta(minutes=30),
        )

    def test_valid_token_updates_password_and_returns_200(self):
        response = self.client.post(
            self.url,
            {"token": "valid-token", "new_password": "new-correct-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-correct-1"))
        self.reset_token.refresh_from_db()
        self.assertIsNotNone(self.reset_token.used_at)

    def test_used_token_cannot_be_reused(self):
        self.client.post(
            self.url,
            {"token": "valid-token", "new_password": "new-correct-1"},
            format="json",
        )

        response = self.client.post(
            self.url,
            {"token": "valid-token", "new_password": "another-pw-2"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_expired_token_returns_400(self):
        self.reset_token.expires_at = timezone.now() - timedelta(seconds=1)
        self.reset_token.save()

        response = self.client.post(
            self.url,
            {"token": "valid-token", "new_password": "new-correct-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unknown_token_returns_400(self):
        response = self.client.post(
            self.url,
            {"token": "does-not-exist", "new_password": "new-correct-1"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_weak_new_password_returns_400(self):
        response = self.client.post(
            self.url, {"token": "valid-token", "new_password": "1234"}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("correct-horse-battery"))
