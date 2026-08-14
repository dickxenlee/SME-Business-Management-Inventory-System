import csv
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from inventory.models import StockMovement
from products.models import Product

from .test_utils import create_invoice, create_sale, local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class ReportExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff = get_user_model().objects.create_user(username="@staff-export")
        cls.staff.groups.add(group)
        cls.admin = get_user_model().objects.create_superuser(username="export-admin")
        cls.product = Product.objects.create(
            sku="=SKU", name="+cmd", selling_price=Decimal("12.50"),
            cost_price=Decimal("5.00"), current_stock=10,
        )
        cls.inactive = Product.objects.create(
            sku="OFF", name="Inactive", selling_price=10, cost_price=5,
            current_stock=1, is_active=False,
        )

    def rows(self, response):
        body = b"".join(response.streaming_content).decode("utf-8")
        return list(csv.reader(StringIO(body)))

    def test_sales_csv_has_one_row_per_sale_and_does_not_repeat_total(self):
        sale = create_sale(
            user=self.staff, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "12.50")],
        )
        create_invoice(sale=sale, user=self.staff, at=local_datetime(2026, 8, 14))
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse("reports:sales_csv"), {"period": "today"}
        )
        rows = self.rows(response)

        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertRegex(response["Content-Disposition"], r'sales-\d{4}-\d{2}-\d{2}\.csv')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], sale.sale_number)
        self.assertEqual(rows[1][4], "12.50")
        self.assertEqual(rows[1][5], sale.invoice.invoice_number)

    def test_sales_csv_sanitizes_customer_and_username_formula_prefixes(self):
        sale = create_sale(
            user=self.staff, at=local_datetime(2026, 8, 14),
            items=[(self.product, 1, "12.50")],
        )
        sale.customer_name = "=SUM(A1:A2)"
        sale.save(update_fields=["customer_name"])
        self.client.force_login(self.staff)

        row = self.rows(self.client.get(reverse("reports:sales_csv"), {"period": "today"}))[1]

        self.assertEqual(row[2], "'=SUM(A1:A2)")
        self.assertEqual(row[6], "'@staff-export")

    def test_inventory_csv_sanitizes_text_without_corrupting_numeric_cells(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type="STOCK_IN",
            quantity=3,
            previous_stock=7,
            new_stock=10,
            reason="-1+1",
            performed_by=self.staff,
        )
        StockMovement.objects.filter(pk=movement.pk).update(
            created_at=local_datetime(2026, 8, 14)
        )
        self.client.force_login(self.staff)

        row = self.rows(
            self.client.get(
                reverse("reports:inventory_movements_csv"), {"period": "today"}
            )
        )[1]

        self.assertEqual(row[1], "'=SKU")
        self.assertEqual(row[2], "'+cmd")
        self.assertEqual(row[4:7], ["3", "7", "10"])
        self.assertEqual(row[7], "'-1+1")
        self.assertEqual(row[8], "'@staff-export")

    def test_staff_inventory_csv_excludes_inactive_product_movements(self):
        movement = StockMovement.objects.create(
            product=self.inactive, movement_type="STOCK_IN", quantity=1,
            previous_stock=0, new_stock=1, reason="Historical", performed_by=self.admin,
        )
        StockMovement.objects.filter(pk=movement.pk).update(
            created_at=local_datetime(2026, 8, 14)
        )

        self.client.force_login(self.staff)
        staff_rows = self.rows(self.client.get(
            reverse("reports:inventory_movements_csv"), {"period": "today"}
        ))
        self.client.force_login(self.admin)
        admin_rows = self.rows(self.client.get(
            reverse("reports:inventory_movements_csv"), {"period": "today"}
        ))

        self.assertEqual(len(staff_rows), 1)
        self.assertEqual(len(admin_rows), 2)

    def test_csv_uses_local_half_open_period_boundary(self):
        create_sale(
            user=self.staff, at=local_datetime(2026, 8, 14, 23, 59),
            items=[(self.product, 1, "10.00")],
        )
        create_sale(
            user=self.staff, at=local_datetime(2026, 8, 15, 0, 0),
            items=[(self.product, 1, "20.00")],
        )
        self.client.force_login(self.staff)

        rows = self.rows(self.client.get(
            reverse("reports:sales_csv"), {"period": "today"}
        ))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][4], "10.00")
