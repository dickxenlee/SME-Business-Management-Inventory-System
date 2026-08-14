from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from products.models import Product

from .test_utils import create_sale, local_datetime


class ReportQueryCountTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="query-admin")
        self.product = Product.objects.create(
            sku="QUERY", name="Query Product", selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"), current_stock=10,
        )
        for day in range(1, 6):
            create_sale(
                user=self.user, at=local_datetime(2026, 8, day),
                items=[(self.product, 1, "10.00")],
            )
        self.client.force_login(self.user)

    def test_dashboard_queries_remain_bounded_as_rows_grow(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("core:home"))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 10)

    def test_reports_page_avoids_obvious_n_plus_one_queries(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("reports:index"))
            self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 18)
