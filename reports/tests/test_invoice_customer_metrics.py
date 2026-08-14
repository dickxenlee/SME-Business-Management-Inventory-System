from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from customers.models import Customer
from products.models import Product
from reports.services import get_customer_metrics, get_invoice_metrics, resolve_period

from .test_utils import create_invoice, create_sale, local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class CustomerAndInvoiceMetricTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="metric-admin")
        cls.product = Product.objects.create(
            sku="METRIC", name="Metric Product", selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"), current_stock=20,
        )

    def test_customer_metrics_use_active_distinct_customers_and_walk_ins(self):
        customer = Customer.objects.create(name="Active Customer")
        Customer.objects.filter(pk=customer.pk).update(
            created_at=local_datetime(2026, 8, 14)
        )
        Customer.objects.create(name="Inactive Customer", is_active=False)
        for _ in range(2):
            create_sale(
                user=self.user, customer=customer,
                at=local_datetime(2026, 8, 14),
                items=[(self.product, 1, "10.00")],
            )
        create_sale(
            user=self.user, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "10.00")],
        )

        metrics = get_customer_metrics(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(metrics["active_count"], 1)
        self.assertEqual(metrics["created_in_period"], 1)
        self.assertEqual(metrics["with_sales_in_period"], 1)
        self.assertEqual(metrics["walk_in_sales"], 1)

    def test_invoice_metrics_separate_issue_count_from_sale_based_rate(self):
        sale = create_sale(
            user=self.user, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "100.00")],
        )
        create_invoice(
            sale=sale, user=self.user, at=local_datetime(2026, 8, 20)
        )

        metrics = get_invoice_metrics(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        self.assertEqual(metrics["issued_count"], 0)
        self.assertEqual(metrics["eligible_sales"], 1)
        self.assertEqual(metrics["invoiced_sales"], 1)
        self.assertEqual(metrics["issuance_rate"], Decimal("100.00"))

    def test_invoice_rate_is_unavailable_when_period_has_no_sales(self):
        metrics = get_invoice_metrics(
            resolve_period("today", today=local_datetime(2026, 8, 14).date())
        )

        self.assertIsNone(metrics["issuance_rate"])
