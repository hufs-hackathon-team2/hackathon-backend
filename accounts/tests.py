from datetime import timedelta

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import RefreshToken, User
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


class SignupViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/auth/signup/"

    def test_signup_creates_user_and_returns_tokens(self):
        response = self.client.post(
            self.url, {"email": "new@example.com", "password": "correct-horse-battery"}
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "new@example.com")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotIn("password", response.data)

        user = User.objects.get(email="new@example.com")
        self.assertEqual(response.data["user_id"], user.user_id)
        self.assertEqual(RefreshToken.objects.filter(user=user).count(), 1)
        self.assertEqual(RefreshToken.objects.get(user=user).token, response.data["refresh"])

    def test_signup_duplicate_email_returns_400(self):
        User.objects.create_user(email="dup@example.com", password="correct-horse-battery")

        response = self.client.post(
            self.url, {"email": "dup@example.com", "password": "correct-horse-battery"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_signup_weak_password_returns_400(self):
        response = self.client.post(
            self.url, {"email": "new@example.com", "password": "1234"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())


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
