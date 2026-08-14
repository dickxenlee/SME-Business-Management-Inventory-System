from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from products.models import Product
from reports.services import get_sales_report, resolve_period

from .test_utils import create_sale, local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class SalesReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="report-admin")
        cls.product = Product.objects.create(
            sku="REP-ONE",
            name="Original Product",
            selling_price=Decimal("150.00"),
            cost_price=Decimal("50.00"),
            current_stock=10,
        )

    def test_summary_uses_sale_totals_and_walk_in_count(self):
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 14),
            items=[(self.product, 2, "100.00")],
        )

        report = get_sales_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(report["revenue"], Decimal("200.00"))
        self.assertEqual(report["sale_count"], 1)
        self.assertEqual(report["average_sale"], Decimal("200.00"))
        self.assertEqual(report["walk_in_count"], 1)

    def test_top_product_uses_historical_subtotals_not_current_price(self):
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 14),
            items=[(self.product, 2, "100.00")],
        )

        report = get_sales_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        top = report["top_products_by_revenue"][0]
        self.assertEqual(top["revenue"], Decimal("200.00"))
        self.assertEqual(top["quantity"], 2)

    def test_product_rename_does_not_split_stable_product_group(self):
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 13),
            items=[(self.product, 1, "100.00")],
        )
        self.product.name = "Renamed Product"
        self.product.save(update_fields=["name", "updated_at"])
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "100.00")],
        )

        report = get_sales_report(
            resolve_period("7d", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(len(report["top_products_by_revenue"]), 1)
        top = report["top_products_by_revenue"][0]
        self.assertEqual(top["product_id"], self.product.pk)
        self.assertEqual(top["product__name"], "Renamed Product")
        self.assertEqual(top["revenue"], Decimal("200.00"))

    def test_daily_revenue_zero_fills_every_date_in_the_period(self):
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 12),
            items=[(self.product, 1, "25.00")],
        )

        report = get_sales_report(
            resolve_period("7d", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(len(report["daily_revenue"]), 7)
        self.assertEqual(report["daily_revenue"][0]["date"].isoformat(), "2026-08-08")
        self.assertEqual(report["daily_revenue"][4]["revenue"], Decimal("25.00"))
        self.assertEqual(report["daily_revenue"][6]["revenue"], Decimal("0.00"))

    def test_half_open_bounds_use_kuala_lumpur_calendar_day(self):
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 14, 0, 0),
            items=[(self.product, 1, "10.00")],
        )
        create_sale(
            user=self.user,
            at=local_datetime(2026, 8, 15, 0, 0),
            items=[(self.product, 1, "99.00")],
        )

        report = get_sales_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(report["revenue"], Decimal("10.00"))
        self.assertEqual(report["sale_count"], 1)
