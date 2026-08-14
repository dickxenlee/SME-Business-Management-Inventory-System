from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Product

from .test_utils import create_invoice, create_sale, local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class ReportsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="Staff")
        cls.user = get_user_model().objects.create_user(username="reports-view")
        cls.user.groups.add(group)
        cls.product = Product.objects.create(
            sku="VIEW-REPORT", name="View Report Product",
            selling_price=Decimal("25.00"), cost_price=Decimal("10.00"),
            current_stock=2, low_stock_threshold=3,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_dashboard_renders_kpis_tables_and_safe_chart_payload(self):
        create_sale(
            user=self.user, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "25.00")],
        )

        with self.settings(TIME_ZONE="Asia/Kuala_Lumpur"):
            response = self.client.get(reverse("core:home"), {"period": "30d"})

        self.assertTemplateUsed(response, "core/home.html")
        self.assertContains(response, "Sales revenue")
        self.assertContains(response, "Active customers")
        self.assertContains(response, "Inventory health")
        self.assertContains(response, "Invoice issuance rate")
        self.assertContains(response, 'id="dashboard-revenue-data"')
        self.assertContains(response, "chart.js")

    def test_invalid_period_falls_back_to_thirty_days(self):
        response = self.client.get(reverse("reports:index"), {"period": "unsafe"})

        self.assertEqual(response.context["period"].key, "30d")
        self.assertContains(response, "Last 30 days")

    def test_reports_page_renders_all_four_business_sections_and_exports(self):
        sale = create_sale(
            user=self.user, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "25.00")],
        )
        invoice = create_invoice(
            sale=sale, user=self.user, at=local_datetime(2026, 8, 14)
        )
        response = self.client.get(reverse("reports:index"))

        self.assertTemplateUsed(response, "reports/report.html")
        self.assertContains(response, "Sales performance")
        self.assertContains(response, "Inventory movement")
        self.assertContains(response, "Customer activity")
        self.assertContains(response, "Invoice coverage")
        self.assertContains(response, reverse("reports:sales_csv"))
        self.assertContains(response, reverse("reports:inventory_movements_csv"))
        self.assertContains(response, 'id="reports-top-products-data"')
        self.assertContains(response, sale.sale_number)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(response, reverse("sales:detail", args=[sale.pk]))
        self.assertContains(response, reverse("invoices:detail", args=[invoice.pk]))

    def test_empty_database_shows_readable_empty_states_and_unavailable_rate(self):
        self.product.current_stock = 10
        self.product.save(update_fields=["current_stock", "updated_at"])
        response = self.client.get(reverse("core:home"))

        self.assertNotContains(response, "None")
        self.assertContains(response, "No sales in this period")
        self.assertContains(response, "No products need stock attention")
        self.assertContains(response, "—")

    def test_navigation_links_to_reports(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("reports:index"))

    def test_non_reporting_page_does_not_load_chart_js(self):
        response = self.client.get(reverse("products:list"))

        self.assertNotContains(response, "chart.js")
