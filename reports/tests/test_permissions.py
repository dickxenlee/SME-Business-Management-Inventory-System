from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse


class ReportsPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff = get_user_model().objects.create_user(username="reports-staff")
        cls.staff.groups.add(staff_group)
        cls.admin = get_user_model().objects.create_superuser(username="reports-admin")
        cls.unassigned = get_user_model().objects.create_user(username="reports-other")
        cls.urls = (
            reverse("reports:index"),
            reverse("reports:sales_csv"),
            reverse("reports:inventory_movements_csv"),
        )

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("core:login"), response.url)

    def test_staff_and_admin_can_access_reports_and_exports(self):
        for user in (self.staff, self.admin):
            self.client.force_login(user)
            for url in self.urls:
                with self.subTest(user=user.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 200)
            self.client.logout()

    def test_authenticated_user_without_role_receives_forbidden(self):
        self.client.force_login(self.unassigned)

        for url in self.urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
