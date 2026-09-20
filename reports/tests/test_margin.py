from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from products.models import Product
from reports.services import get_dashboard_data, get_sales_report, resolve_period

from .test_utils import create_sale, days_ago


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class GrossMarginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="Staff")
        cls.user = get_user_model().objects.create_user(username="margin-user")
        cls.user.groups.add(group)
        cls.product = Product.objects.create(
            sku="MARGIN-1",
            name="Margin Product",
            selling_price=Decimal("25.00"),
            cost_price=Decimal("10.00"),
            current_stock=100,
        )

    def period(self):
        return resolve_period("30d")

    def test_gross_profit_and_rate_come_from_the_cost_snapshot(self):
        create_sale(
            user=self.user, at=days_ago(2),
            items=[(self.product, 4, "25.00")],
        )

        margin = get_sales_report(self.period())["margin"]

        self.assertEqual(margin["cost"], Decimal("40.00"))
        self.assertEqual(margin["gross_profit"], Decimal("60.00"))
        self.assertEqual(margin["margin_rate"], Decimal("60.00"))
        self.assertTrue(margin["cost_is_complete"])
        self.assertEqual(margin["uncosted_items"], 0)

    def test_repricing_the_product_does_not_rewrite_historical_margin(self):
        create_sale(
            user=self.user, at=days_ago(2),
            items=[(self.product, 4, "25.00")],
        )

        self.product.cost_price = Decimal("22.00")
        self.product.selling_price = Decimal("30.00")
        self.product.save(update_fields=["cost_price", "selling_price", "updated_at"])

        margin = get_sales_report(self.period())["margin"]

        self.assertEqual(margin["cost"], Decimal("40.00"))
        self.assertEqual(margin["gross_profit"], Decimal("60.00"))

    def test_uncosted_lines_are_excluded_and_disclosed_not_guessed(self):
        create_sale(
            user=self.user, at=days_ago(2),
            items=[(self.product, 4, "25.00")],
        )
        create_sale(
            user=self.user, at=days_ago(1),
            items=[(self.product, 2, "25.00")],
            record_cost=False,
        )

        margin = get_sales_report(self.period())["margin"]

        # Only the costed line contributes; the legacy line is reported, not
        # back-filled from the Product's current cost_price.
        self.assertEqual(margin["cost"], Decimal("40.00"))
        self.assertEqual(margin["gross_profit"], Decimal("60.00"))
        self.assertEqual(margin["costed_items"], 1)
        self.assertEqual(margin["uncosted_items"], 1)
        self.assertFalse(margin["cost_is_complete"])

    def test_margin_rate_is_none_when_nothing_is_costed(self):
        create_sale(
            user=self.user, at=days_ago(2),
            items=[(self.product, 4, "25.00")],
            record_cost=False,
        )

        margin = get_sales_report(self.period())["margin"]

        self.assertIsNone(margin["margin_rate"])
        self.assertEqual(margin["gross_profit"], Decimal("0.00"))

    def test_dashboard_exposes_the_same_margin_block(self):
        create_sale(
            user=self.user, at=days_ago(2),
            items=[(self.product, 4, "25.00")],
        )

        margin = get_dashboard_data(self.period(), self.user)["margin"]

        self.assertEqual(margin["gross_profit"], Decimal("60.00"))
        self.assertEqual(margin["margin_rate"], Decimal("60.00"))
