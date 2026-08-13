from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class DashboardPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(
            username="staff-user",
            password="test-password-123",
        )
        cls.staff_user.groups.add(cls.staff_group)
        cls.unassigned_user = user_model.objects.create_user(
            username="unassigned-user",
            password="test-password-123",
        )
        cls.admin_user = user_model.objects.create_superuser(
            username="admin-user",
            password="test-password-123",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("core:home"))

        self.assertRedirects(
            response,
            f'{reverse("core:login")}?next={reverse("core:home")}',
        )

    def test_staff_group_member_can_access_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_dashboard(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_without_role_receives_forbidden(self):
        self.client.force_login(self.unassigned_user)

        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, "403.html")

