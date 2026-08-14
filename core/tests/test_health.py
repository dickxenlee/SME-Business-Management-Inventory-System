from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_get_reports_healthy_database_without_authentication(self):
        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_head_reports_health_without_response_body(self):
        response = self.client.head(reverse("core:health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    @patch("core.views.connection.cursor")
    def test_database_failure_returns_generic_unavailable_response(self, cursor):
        cursor.side_effect = OperationalError(
            "password=do-not-leak host=private-database.example.com"
        )

        response = self.client.get(reverse("core:health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertNotContains(response, "do-not-leak", status_code=503)
        self.assertNotContains(
            response, "private-database.example.com", status_code=503
        )
