from django.test import SimpleTestCase
from django.urls import reverse


class HomePageTests(SimpleTestCase):
    def test_home_page_renders_dashboard_template(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_home_page_contains_navigation_and_dashboard_heading(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, "<nav", html=False)
        self.assertContains(response, "Dashboard")

    def test_unknown_url_returns_not_found(self):
        response = self.client.get("/missing-page/")

        self.assertEqual(response.status_code, 404)
