from django.db import IntegrityError
from django.test import TestCase

from .models import User
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
