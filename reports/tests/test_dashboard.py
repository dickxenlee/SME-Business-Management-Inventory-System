from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from products.models import Product
from reports.services import get_dashboard_data, get_sales_report, resolve_period

from .test_utils import create_invoice, create_sale, local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class DashboardDataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="dashboard-admin")
        self.product = Product.objects.create(
            sku="DASH", name="Dashboard Product", selling_price=Decimal("100.00"),
            cost_price=Decimal("50.00"), current_stock=5,
        )

    def test_invoice_does_not_double_count_sale_revenue(self):
        sale = create_sale(
            user=self.user, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "100.00")],
        )
        create_invoice(
            sale=sale, user=self.user, at=local_datetime(2026, 8, 14)
        )

        data = get_dashboard_data(
            resolve_period("today", today=local_datetime(2026, 8, 14).date()),
            self.user,
        )

        self.assertEqual(data["revenue"], Decimal("100.00"))
        self.assertEqual(data["sale_count"], 1)
        self.assertEqual(data["invoice_rate"], Decimal("100.00"))

        sales_report = get_sales_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )
        self.assertEqual(sales_report["revenue"], Decimal("100.00"))

    def test_recent_sales_are_limited_to_ten(self):
        for day in range(1, 12):
            create_sale(
                user=self.user, at=local_datetime(2026, 8, day),
                items=[(self.product, 1, "1.00")],
            )

        data = get_dashboard_data(
            resolve_period("30d", today=local_datetime(2026, 8, 14).date()),
            self.user,
        )

        self.assertEqual(len(data["recent_sales"]), 10)
        self.assertGreater(
            data["recent_sales"][0].created_at,
            data["recent_sales"][-1].created_at,
        )
