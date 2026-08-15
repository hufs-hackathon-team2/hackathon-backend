from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User


class PushPermissionViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/notifications/permission/"
        self.user = User.objects.create_user(
            email="push@example.com", password="correct-horse-battery"
        )
        login_response = self.client.post(
            "/auth/login/",
            {"email": "push@example.com", "password": "correct-horse-battery"},
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

    def test_grant_permission_updates_user(self):
        response = self.client.post(self.url, {"granted": True}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["push_permission_granted"], True)
        self.user.refresh_from_db()
        self.assertTrue(self.user.push_permission_granted)

    def test_deny_permission_updates_user(self):
        response = self.client.post(self.url, {"granted": False}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["push_permission_granted"], False)

    def test_without_auth_returns_401(self):
        self.client.credentials()

        response = self.client.post(self.url, {"granted": True}, format="json")

        self.assertEqual(response.status_code, 401)
