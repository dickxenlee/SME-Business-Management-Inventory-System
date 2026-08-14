from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice, InvoiceItem
from sales.models import Sale


class InvoiceAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="invoice-admin-user",
            password="test-password-123",
        )
        cls.sale = Sale.objects.create(
            customer_name="Admin Customer",
            customer_address="Admin Customer Address",
            total_amount=Decimal("30.00"),
            created_by=cls.admin_user,
        )
        cls.invoice = Invoice.objects.create(
            sale=cls.sale,
            customer_name=cls.sale.customer_name,
            customer_address=cls.sale.customer_address,
            seller_name="Admin SME",
            seller_address="Admin Business Address",
            total_amount=cls.sale.total_amount,
            issued_by=cls.admin_user,
        )
        cls.item = InvoiceItem.objects.create(
            invoice=cls.invoice,
            product_sku="ADMIN-INV",
            product_name="Admin Invoice Product",
            quantity=2,
            unit_price=Decimal("15.00"),
            subtotal=Decimal("30.00"),
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_invoice_admin_is_registered_for_read_only_visibility(self):
        response = self.client.get("/admin/invoices/invoice/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.invoice.invoice_number)

    def test_invoice_admin_displays_read_only_invoice_and_items(self):
        response = self.client.get(
            reverse("admin:invoices_invoice_change", args=[self.invoice.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.invoice.invoice_number)
        self.assertContains(response, self.item.product_sku)

    def test_invoice_admin_rejects_add_change_and_delete(self):
        responses = (
            self.client.get(reverse("admin:invoices_invoice_add")),
            self.client.post(
                reverse("admin:invoices_invoice_change", args=[self.invoice.pk]),
                {"total_amount": "999.00", "_save": "Save"},
            ),
            self.client.get(
                reverse("admin:invoices_invoice_delete", args=[self.invoice.pk])
            ),
        )

        self.assertTrue(all(response.status_code == 403 for response in responses))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal("30.00"))

    def test_invoice_item_admin_rejects_add_change_and_delete(self):
        responses = (
            self.client.get(reverse("admin:invoices_invoiceitem_add")),
            self.client.post(
                reverse(
                    "admin:invoices_invoiceitem_change",
                    args=[self.item.pk],
                ),
                {"quantity": "99", "_save": "Save"},
            ),
            self.client.get(
                reverse(
                    "admin:invoices_invoiceitem_delete",
                    args=[self.item.pk],
                )
            ),
        )

        self.assertTrue(all(response.status_code == 403 for response in responses))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 2)

    def test_invoice_deletion_is_not_available_as_bulk_action(self):
        response = self.client.get(reverse("admin:invoices_invoice_changelist"))

        self.assertNotContains(response, 'value="delete_selected"')
        self.assertTrue(InvoiceItem.objects.filter(pk=self.item.pk).exists())
