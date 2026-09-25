from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings

from customers.models import Customer
from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale
from sales.services import create_sale

from invoices import services
from invoices.models import Invoice, InvoiceItem


class InvoiceServiceAvailabilityTests(SimpleTestCase):
    def test_issue_invoice_service_is_available(self):
        self.assertTrue(hasattr(services, "issue_invoice"))
        self.assertTrue(hasattr(services, "InvoiceOperationError"))


@override_settings(
    INVOICE_SELLER_NAME="Configured SME",
    INVOICE_SELLER_ADDRESS="12 Business Road\nKuala Lumpur",
)
class IssueInvoiceServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="invoice-issuer")
        self.customer = Customer.objects.create(
            name="ABC Trading",
            address="Original Customer Address",
        )
        self.product_a = Product.objects.create(
            sku="INV-A",
            name="Keyboard",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("50.00"),
            current_stock=10,
        )
        self.product_b = Product.objects.create(
            sku="INV-B",
            name="Mouse",
            selling_price=Decimal("25.00"),
            cost_price=Decimal("10.00"),
            current_stock=10,
        )

    def create_source_sale(self, *, customer=True, multiple=False):
        items = [{"product_id": self.product_a.pk, "quantity": 2}]
        if multiple:
            items.append({"product_id": self.product_b.pk, "quantity": 3})
        return create_sale(
            customer_id=self.customer.pk if customer else None,
            items=items,
            created_by=self.user,
        )

    def test_issue_invoice_copies_historical_sale_snapshots_without_side_effects(self):
        sale = self.create_source_sale(multiple=True)
        original_sale_values = (
            sale.customer_name,
            sale.customer_address,
            sale.total_amount,
        )
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        original_stocks = (self.product_a.current_stock, self.product_b.current_stock)
        original_movement_count = StockMovement.objects.count()

        self.customer.name = "Renamed Customer"
        self.customer.address = "Changed Address"
        self.customer.save()
        self.product_a.sku = "CHANGED-A"
        self.product_a.name = "Changed Keyboard"
        self.product_a.selling_price = Decimal("999.00")
        self.product_a.save()

        invoice = services.issue_invoice(sale_id=sale.pk, issued_by=self.user)

        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.sale, sale)
        self.assertEqual(invoice.customer_name, "ABC Trading")
        self.assertEqual(invoice.customer_address, "Original Customer Address")
        self.assertEqual(invoice.seller_name, "Configured SME")
        self.assertEqual(invoice.seller_address, "12 Business Road\nKuala Lumpur")
        self.assertEqual(invoice.total_amount, Decimal("275.00"))
        self.assertEqual(invoice.issued_by, self.user)
        self.assertIsNotNone(invoice.issued_at)
        self.assertEqual(
            list(
                invoice.items.values_list(
                    "product_sku",
                    "product_name",
                    "quantity",
                    "unit_price",
                    "subtotal",
                )
            ),
            [
                ("INV-A", "Keyboard", 2, Decimal("100.00"), Decimal("200.00")),
                ("INV-B", "Mouse", 3, Decimal("25.00"), Decimal("75.00")),
            ],
        )

        sale.refresh_from_db()
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(
            (sale.customer_name, sale.customer_address, sale.total_amount),
            original_sale_values,
        )
        self.assertEqual(
            (self.product_a.current_stock, self.product_b.current_stock),
            original_stocks,
        )
        self.assertEqual(StockMovement.objects.count(), original_movement_count)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(InvoiceItem.objects.count(), 2)

    @override_settings(INVOICE_SELLER_NAME="", INVOICE_SELLER_ADDRESS="")
    def test_missing_seller_configuration_is_rejected_without_persistence(self):
        sale = self.create_source_sale()

        with self.assertRaisesMessage(
            services.InvoiceOperationError,
            "Invoice seller name and address must be configured before issuing",
        ):
            services.issue_invoice(sale_id=sale.pk, issued_by=self.user)

        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(InvoiceItem.objects.exists())

    def test_repeated_issuance_returns_existing_invoice_without_changes(self):
        sale = self.create_source_sale()
        invoice = services.issue_invoice(sale_id=sale.pk, issued_by=self.user)
        original_values = (
            invoice.seller_name,
            invoice.seller_address,
            invoice.issued_by_id,
            invoice.issued_at,
        )
        other_user = get_user_model().objects.create_user(username="other-issuer")

        with override_settings(
            INVOICE_SELLER_NAME="Changed Seller",
            INVOICE_SELLER_ADDRESS="Changed Seller Address",
        ):
            repeated = services.issue_invoice(
                sale_id=sale.pk,
                issued_by=other_user,
            )

        repeated.refresh_from_db()
        self.assertEqual(repeated.pk, invoice.pk)
        self.assertEqual(
            (
                repeated.seller_name,
                repeated.seller_address,
                repeated.issued_by_id,
                repeated.issued_at,
            ),
            original_values,
        )
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(InvoiceItem.objects.count(), 1)

    def test_sale_without_items_is_rejected(self):
        sale = Sale.objects.create(
            customer_name="",
            customer_address="",
            net_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
            created_by=self.user,
        )

        with self.assertRaisesMessage(
            services.InvoiceOperationError,
            "Sale has no items and cannot be invoiced",
        ):
            services.issue_invoice(sale_id=sale.pk, issued_by=self.user)

        self.assertFalse(Invoice.objects.exists())

    def test_database_refuses_to_desync_a_sale_total_from_its_net(self):
        """The invariant now lives in the database, not only in the service.

        issue_invoice still checks it, because a database restored from a dump
        taken before this constraint existed could hold a desynced Sale.
        """
        sale = self.create_source_sale()

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Sale.objects.filter(pk=sale.pk).update(
                    total_amount=Decimal("999.00")
                )

        self.assertFalse(Invoice.objects.exists())

    def test_database_refuses_a_line_whose_subtotal_does_not_add_up(self):
        """Repricing a line without restating its subtotal is now impossible.

        Previously only issue_invoice caught this, and only at issuance time;
        the corrupt row could sit in the table until someone tried to invoice.
        """
        sale = self.create_source_sale()

        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                sale.items.update(unit_price=Decimal("50.00"))

        self.assertFalse(Invoice.objects.exists())

    def test_invoice_item_failure_rolls_back_the_complete_issuance(self):
        sale = self.create_source_sale()
        self.product_a.refresh_from_db()
        original_stock = self.product_a.current_stock
        original_movements = StockMovement.objects.count()
        original_sale_values = (sale.total_amount, sale.customer_name)

        with patch(
            "invoices.services.InvoiceItem.objects.bulk_create",
            side_effect=IntegrityError("simulated InvoiceItem failure"),
        ):
            with self.assertRaises(IntegrityError):
                services.issue_invoice(sale_id=sale.pk, issued_by=self.user)

        sale.refresh_from_db()
        self.product_a.refresh_from_db()
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(InvoiceItem.objects.exists())
        self.assertEqual(
            (sale.total_amount, sale.customer_name),
            original_sale_values,
        )
        self.assertEqual(self.product_a.current_stock, original_stock)
        self.assertEqual(StockMovement.objects.count(), original_movements)

    def test_walk_in_sale_is_invoiceable(self):
        sale = self.create_source_sale(customer=False)

        invoice = services.issue_invoice(sale_id=sale.pk, issued_by=self.user)

        self.assertEqual(invoice.customer_name, "")
        self.assertEqual(invoice.customer_address, "")
        self.assertEqual(invoice.items.count(), 1)

    def test_issued_snapshots_do_not_follow_later_source_or_setting_changes(self):
        sale = self.create_source_sale()
        invoice = services.issue_invoice(sale_id=sale.pk, issued_by=self.user)
        original_invoice_values = (
            invoice.customer_name,
            invoice.customer_address,
            invoice.seller_name,
            invoice.seller_address,
            invoice.total_amount,
        )
        original_item_values = list(
            invoice.items.values_list(
                "product_sku",
                "product_name",
                "unit_price",
                "subtotal",
            )
        )

        self.customer.name = "Later Customer Name"
        self.customer.address = "Later Customer Address"
        self.customer.is_active = False
        self.customer.save()
        self.product_a.sku = "LATER-SKU"
        self.product_a.name = "Later Product Name"
        self.product_a.selling_price = Decimal("777.00")
        self.product_a.is_active = False
        self.product_a.save()
        Sale.objects.filter(pk=sale.pk).update(
            customer_name="Later Sale Customer",
            customer_address="Later Sale Address",
            net_amount=Decimal("999.00"),
            total_amount=Decimal("999.00"),
        )

        with override_settings(
            INVOICE_SELLER_NAME="Later Seller",
            INVOICE_SELLER_ADDRESS="Later Seller Address",
        ):
            invoice.refresh_from_db()
            self.assertEqual(
                (
                    invoice.customer_name,
                    invoice.customer_address,
                    invoice.seller_name,
                    invoice.seller_address,
                    invoice.total_amount,
                ),
                original_invoice_values,
            )
            self.assertEqual(
                list(
                    invoice.items.values_list(
                        "product_sku",
                        "product_name",
                        "unit_price",
                        "subtotal",
                    )
                ),
                original_item_values,
            )

    def test_missing_sale_is_rejected_clearly(self):
        with self.assertRaisesMessage(
            services.InvoiceOperationError,
            "Sale is not available",
        ):
            services.issue_invoice(sale_id=999999, issued_by=self.user)
