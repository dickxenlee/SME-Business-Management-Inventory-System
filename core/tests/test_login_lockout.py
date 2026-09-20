from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
class LoginLockoutTests(TestCase):
    """The public login form must not be brute-forceable."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="lockout-target",
            password="test-password-123",
        )

    def attempt(self, password, **extra):
        return self.client.post(
            reverse("core:login"),
            {"username": "lockout-target", "password": password},
            **extra,
        )

    def test_repeated_failures_lock_the_login_out(self):
        for _ in range(2):
            self.assertEqual(self.attempt("wrong").status_code, 200)

        locked = self.attempt("wrong")

        self.assertEqual(locked.status_code, 429)
        self.assertContains(
            locked, "Too many sign-in attempts", status_code=429
        )

    def test_lockout_blocks_even_the_correct_password(self):
        for _ in range(3):
            self.attempt("wrong")

        response = self.attempt("test-password-123")

        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_a_success_before_the_limit_resets_the_counter(self):
        self.attempt("wrong")
        self.attempt("wrong")

        self.assertEqual(self.attempt("test-password-123").status_code, 302)
        self.client.logout()

        # The counter reset on success, so two more failures must not lock.
        self.attempt("wrong")
        self.assertEqual(self.attempt("wrong").status_code, 200)

    def test_lockout_is_scoped_to_the_attacking_address(self):
        for _ in range(3):
            self.attempt("wrong", REMOTE_ADDR="203.0.113.10")

        self.assertEqual(
            self.attempt("wrong", REMOTE_ADDR="203.0.113.10").status_code, 429
        )
        # The real user, elsewhere, must still be able to sign in: locking on
        # username alone would let anyone lock a known account out of itself.
        self.assertEqual(
            self.attempt(
                "test-password-123", REMOTE_ADDR="198.51.100.20"
            ).status_code,
            302,
        )
