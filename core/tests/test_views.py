from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.templatetags.static import static
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = get_user_model().objects.create_user(
            username="staff-user",
            password="test-password-123",
        )
        cls.staff_user.groups.add(staff_group)

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_home_page_renders_dashboard_template(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_home_page_contains_navigation_dashboard_and_favicon(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "<nav", html=False)
        self.assertContains(response, "Dashboard")
        self.assertContains(
            response,
            f'<link rel="icon" href="{static("img/favicon.svg")}" type="image/svg+xml">',
            html=True,
        )

    def test_unknown_url_returns_not_found(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
