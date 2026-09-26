from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from sales.models import Sale

from invoices import models


class InvoiceModelAvailabilityTests(SimpleTestCase):
    def test_invoice_models_are_available(self):
        self.assertTrue(hasattr(models, "Invoice"))
        self.assertTrue(hasattr(models, "InvoiceItem"))

    def test_invoice_models_expose_the_approved_snapshot_fields(self):
        invoice_fields = {field.name for field in models.Invoice._meta.fields}
        item_fields = {field.name for field in models.InvoiceItem._meta.fields}

        self.assertTrue(
            {
                "sale",
                "customer_name",
                "customer_address",
                "seller_name",
                "seller_address",
                "total_amount",
                "issued_by",
                "issued_at",
            }.issubset(invoice_fields)
        )
        self.assertTrue(
            {
                "invoice",
                "product_sku",
                "product_name",
                "quantity",
                "unit_price",
                "subtotal",
            }.issubset(item_fields)
        )


class InvoiceModelDatabaseTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="invoice-model-user")
        self.sale = Sale.objects.create(
            customer_name="Model Customer",
            customer_address="Model Address",
            net_amount=Decimal("25.00"),
            total_amount=Decimal("25.00"),
            created_by=self.user,
        )

    def create_invoice(self, **overrides):
        values = {
            "sale": self.sale,
            "customer_name": "Model Customer",
            "customer_address": "Model Address",
            "seller_name": "Example SME",
            "seller_address": "Example Business Address",
            "total_amount": Decimal("25.00"),
            "issued_by": self.user,
        }
        values.update(overrides)
        # Untaxed fixture, so net mirrors the total the caller asked for.
        values.setdefault("net_amount", values["total_amount"])
        return models.Invoice.objects.create(**values)

    def test_invoice_number_is_derived_from_primary_key(self):
        invoice = self.create_invoice()

        self.assertEqual(invoice.invoice_number, f"INV-{invoice.pk:06d}")
        self.assertEqual(str(invoice), invoice.invoice_number)

    def test_sale_can_have_only_one_invoice(self):
        self.create_invoice()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_invoice()

    def test_invoice_protects_its_sale(self):
        self.create_invoice()

        with self.assertRaises(ProtectedError):
            self.sale.delete()

    def test_deleting_issuer_preserves_invoice(self):
        invoice = self.create_invoice()

        self.user.delete()
        invoice.refresh_from_db()

        self.assertIsNone(invoice.issued_by)

    def test_negative_invoice_total_is_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_invoice(total_amount=Decimal("-0.01"))

    def test_invoice_item_constraints_reject_invalid_values(self):
        invoice = self.create_invoice()
        invalid_values = (
            {"quantity": 0, "unit_price": Decimal("1.00"), "subtotal": Decimal("1.00")},
            {"quantity": 1, "unit_price": Decimal("-0.01"), "subtotal": Decimal("1.00")},
            {"quantity": 1, "unit_price": Decimal("1.00"), "subtotal": Decimal("-0.01")},
        )

        for values in invalid_values:
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    models.InvoiceItem.objects.create(
                        invoice=invoice,
                        product_sku="MODEL-ITEM",
                        product_name="Model Item",
                        **values,
                    )
