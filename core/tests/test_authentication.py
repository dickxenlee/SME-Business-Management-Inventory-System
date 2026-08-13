from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(
            username="staff-user",
            password="test-password-123",
        )
        cls.staff_user.groups.add(staff_group)
        cls.inactive_user = user_model.objects.create_user(
            username="inactive-user",
            password="test-password-123",
            is_active=False,
        )

    def test_login_page_uses_authentication_template(self):
        response = self.client.get(reverse("core:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, 'class="form-control"')
        self.assertNotContains(response, "Register")
        self.assertNotContains(response, "Reset password")

    def test_valid_staff_credentials_log_user_in(self):
        response = self.client.post(
            reverse("core:login"),
            {"username": "staff-user", "password": "test-password-123"},
        )

        self.assertRedirects(response, reverse("core:home"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.staff_user.pk))

    def test_invalid_credentials_show_generic_error(self):
        response = self.client.post(
            reverse("core:login"),
            {"username": "staff-user", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct username and password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_log_in(self):
        response = self.client.post(
            reverse("core:login"),
            {"username": "inactive-user", "password": "test-password-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_safe_next_url_is_preserved_after_login(self):
        login_url = f'{reverse("core:login")}?next={reverse("core:home")}'

        response = self.client.post(
            login_url,
            {
                "username": "staff-user",
                "password": "test-password-123",
                "next": reverse("core:home"),
            },
        )

        self.assertRedirects(response, reverse("core:home"))

    def test_external_next_url_is_rejected(self):
        response = self.client.post(
            reverse("core:login"),
            {
                "username": "staff-user",
                "password": "test-password-123",
                "next": "https://example.com/steal-session",
            },
        )

        self.assertRedirects(response, reverse("core:home"))

    def test_post_logout_ends_session_and_redirects_to_login(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse("core:logout"))

        self.assertRedirects(response, reverse("core:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_logout_is_rejected(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("core:logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff_user)

        response = csrf_client.post(reverse("core:logout"))

        self.assertEqual(response.status_code, 403)

