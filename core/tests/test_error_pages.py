from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.views import defaults


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ProductionErrorPageTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    def assert_error_response(self, response, status_code, heading):
        self.assertEqual(response.status_code, status_code)
        self.assertInHTML(f"<h1>{heading}</h1>", response.content.decode())
        self.assertNotContains(response, "Traceback", status_code=status_code)

    def test_bad_request_uses_safe_custom_page(self):
        response = defaults.bad_request(self.request, Exception("private detail"))

        self.assert_error_response(response, 400, "Bad request")
        self.assertNotContains(response, "private detail", status_code=400)

    def test_permission_denied_uses_safe_custom_page(self):
        response = defaults.permission_denied(
            self.request, Exception("private permission detail")
        )

        self.assert_error_response(response, 403, "Permission denied")
        self.assertNotContains(response, "private permission detail", status_code=403)

    def test_unknown_url_uses_safe_custom_page(self):
        response = self.client.get("/unknown-production-route/")

        self.assert_error_response(response, 404, "Page not found")

    def test_server_error_uses_database_independent_custom_page(self):
        response = defaults.server_error(self.request)

        self.assert_error_response(response, 500, "Something went wrong")

    def test_csrf_failure_uses_safe_custom_page(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("core:logout"))

        self.assert_error_response(response, 403, "Request verification failed")
        self.assertNotContains(response, "CSRF token", status_code=403)
