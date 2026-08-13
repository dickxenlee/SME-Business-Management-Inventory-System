from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class AdminPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(
            username="staff-user",
            password="test-password-123",
        )
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(
            username="admin-user",
            password="test-password-123",
        )

    def test_normal_staff_user_is_not_django_staff(self):
        self.assertFalse(self.staff_user.is_staff)

    def test_staff_user_cannot_access_django_admin(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin:index"))

        self.assertRedirects(
            response,
            f'{reverse("admin:login")}?next={reverse("admin:index")}',
        )

    def test_superuser_can_access_django_admin(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)

    def test_superuser_can_access_user_management(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:auth_user_changelist"))

        self.assertEqual(response.status_code, 200)

    def test_staff_navigation_hides_admin_link(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "staff-user")
        self.assertContains(response, "Logout")
        self.assertNotContains(response, reverse("admin:index"))

    def test_superuser_navigation_shows_admin_link(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("admin:index"))

