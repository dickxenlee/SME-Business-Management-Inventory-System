from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.models import CreditNote, Invoice
from invoices.services import (
    CreditNoteOperationError,
    InvoiceOperationError,
    issue_credit_note,
    issue_invoice,
)
from products.models import Product
from reports.services import get_sales_report, resolve_period
from sales.models import Sale
from sales.services import SalesOperationError, create_sale, void_sale


@override_settings(
    INVOICE_SELLER_NAME="Aman Trading", INVOICE_SELLER_ADDRESS="Kuala Lumpur"
)
class IssueCreditNoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="credit-owner", password="test-password-123"
        )

    def setUp(self):
        self.product = Product.objects.create(
            sku="CN-1",
            name="Credited Product",
            selling_price=Decimal("50.00"),
            cost_price=Decimal("20.00"),
            current_stock=10,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            created_by=self.user,
        )
        self.invoice = issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

    def test_a_credit_note_returns_the_stock(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 8)

        issue_credit_note(
            invoice_id=self.invoice.pk, reason="Goods faulty", issued_by=self.user
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)

    def test_the_invoice_and_sale_are_left_untouched(self):
        """The customer holds that Invoice, so it must not be rewritten."""
        before = (
            self.invoice.total_amount,
            self.invoice.net_amount,
            self.invoice.items.count(),
            self.sale.total_amount,
        )

        issue_credit_note(
            invoice_id=self.invoice.pk, reason="Wrong item", issued_by=self.user
        )

        self.invoice.refresh_from_db()
        self.sale.refresh_from_db()
        self.assertEqual(
            (
                self.invoice.total_amount,
                self.invoice.net_amount,
                self.invoice.items.count(),
                self.sale.total_amount,
            ),
            before,
        )

    def test_the_credit_note_copies_the_invoice_figures_and_lines(self):
        credit_note = issue_credit_note(
            invoice_id=self.invoice.pk, reason="Returned", issued_by=self.user
        )

        self.assertEqual(credit_note.net_amount, self.invoice.net_amount)
        self.assertEqual(credit_note.tax_amount, self.invoice.tax_amount)
        self.assertEqual(credit_note.total_amount, self.invoice.total_amount)
        self.assertEqual(credit_note.seller_name, self.invoice.seller_name)
        self.assertEqual(credit_note.items.count(), self.invoice.items.count())
        self.assertEqual(credit_note.items.get().product_sku, "CN-1")

    def test_the_credit_note_is_numbered(self):
        credit_note = issue_credit_note(
            invoice_id=self.invoice.pk, reason="Returned", issued_by=self.user
        )

        self.assertEqual(
            credit_note.credit_note_number, f"CN-{credit_note.pk:06d}"
        )

    @override_settings(SALES_TAX_RATE=Decimal("6"))
    def test_tax_charged_is_credited_back(self):
        """The shop reclaims the tax it collected, so it must be on the note."""
        taxed_sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            created_by=self.user,
        )
        taxed_invoice = issue_invoice(sale_id=taxed_sale.pk, issued_by=self.user)

        credit_note = issue_credit_note(
            invoice_id=taxed_invoice.pk, reason="Returned", issued_by=self.user
        )

        self.assertEqual(credit_note.net_amount, Decimal("50.00"))
        self.assertEqual(credit_note.tax_amount, Decimal("3.00"))
        self.assertEqual(credit_note.total_amount, Decimal("53.00"))
        self.assertEqual(credit_note.tax_label, "SST")

    def test_an_invoice_cannot_be_credited_twice(self):
        issue_credit_note(
            invoice_id=self.invoice.pk, reason="First", issued_by=self.user
        )

        with self.assertRaisesMessage(
            CreditNoteOperationError, "already been credited"
        ):
            issue_credit_note(
                invoice_id=self.invoice.pk, reason="Second", issued_by=self.user
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)

    def test_a_reason_is_required(self):
        with self.assertRaisesMessage(CreditNoteOperationError, "reason is required"):
            issue_credit_note(
                invoice_id=self.invoice.pk, reason="  ", issued_by=self.user
            )

        self.assertFalse(CreditNote.objects.exists())

    def test_a_missing_invoice_is_rejected_clearly(self):
        with self.assertRaisesMessage(
            CreditNoteOperationError, "Invoice is not available"
        ):
            issue_credit_note(invoice_id=999999, reason="X", issued_by=self.user)

    def test_stock_comes_back_even_if_the_product_was_discontinued(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active", "updated_at"])

        issue_credit_note(
            invoice_id=self.invoice.pk, reason="Discontinued", issued_by=self.user
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)


@override_settings(
    TIME_ZONE="Asia/Kuala_Lumpur",
    USE_TZ=True,
    INVOICE_SELLER_NAME="Aman Trading",
    INVOICE_SELLER_ADDRESS="Kuala Lumpur",
)
class CreditedSalesLeaveRevenueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="credit-report", password="test-password-123"
        )

    def test_a_credited_sale_stops_counting_towards_revenue_and_margin(self):
        product = Product.objects.create(
            sku="CN-REP",
            name="Credited Report Product",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            current_stock=10,
        )
        kept = create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=self.user,
        )
        cancelled = create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=self.user,
        )
        invoice = issue_invoice(sale_id=cancelled.pk, issued_by=self.user)

        before = get_sales_report(resolve_period("30d"))
        self.assertEqual(before["revenue"], Decimal("200.00"))

        issue_credit_note(
            invoice_id=invoice.pk, reason="Returned", issued_by=self.user
        )

        after = get_sales_report(resolve_period("30d"))
        self.assertEqual(after["revenue"], Decimal("100.00"))
        self.assertEqual(after["sale_count"], 1)
        self.assertEqual(after["margin"]["gross_profit"], Decimal("40.00"))
        self.assertEqual([sale.pk for sale in after["recent_sales"]], [kept.pk])

    def test_a_credited_sale_is_left_out_of_the_csv_export(self):
        product = Product.objects.create(
            sku="CN-CSV",
            name="Credited CSV Product",
            selling_price=Decimal("40.00"),
            cost_price=Decimal("15.00"),
            current_stock=10,
        )
        sale = create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=self.user,
        )
        invoice = issue_invoice(sale_id=sale.pk, issued_by=self.user)
        issue_credit_note(
            invoice_id=invoice.pk, reason="Returned", issued_by=self.user
        )

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("reports:sales_csv"), {"period": "30d"}
        )
        body = b"".join(response.streaming_content).decode("utf-8")

        self.assertNotIn(sale.sale_number, body)


@override_settings(
    INVOICE_SELLER_NAME="Aman Trading", INVOICE_SELLER_ADDRESS="Kuala Lumpur"
)
class CreditNoteAccessTests(TestCase):
    """Crediting moves stock and money, so it is owner-only."""

    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.owner = get_user_model().objects.create_superuser(
            username="cn-owner", password="test-password-123"
        )
        cls.shop_staff = get_user_model().objects.create_user(
            username="cn-staff", password="test-password-123"
        )
        cls.shop_staff.groups.add(staff_group)

    def setUp(self):
        self.product = Product.objects.create(
            sku="CN-ACL",
            name="Access Product",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("8.00"),
            current_stock=10,
        )
        sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            created_by=self.owner,
        )
        self.invoice = issue_invoice(sale_id=sale.pk, issued_by=self.owner)

    def test_shop_staff_cannot_issue_a_credit_note(self):
        self.client.force_login(self.shop_staff)

        response = self.client.post(
            reverse("invoices:issue_credit_note", args=[self.invoice.pk]),
            {"reason": "Trying it on"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(CreditNote.objects.exists())

    def test_shop_staff_can_still_read_a_credit_note(self):
        credit_note = issue_credit_note(
            invoice_id=self.invoice.pk, reason="Returned", issued_by=self.owner
        )
        self.client.force_login(self.shop_staff)

        response = self.client.get(
            reverse("invoices:credit_note_detail", args=[credit_note.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, credit_note.credit_note_number)

    def test_an_owner_can_issue_one_through_the_form(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("invoices:issue_credit_note", args=[self.invoice.pk]),
            {"reason": "Customer returned the goods"},
            follow=True,
        )

        credit_note = CreditNote.objects.get()
        self.assertContains(response, credit_note.credit_note_number)
        self.assertEqual(credit_note.reason, "Customer returned the goods")
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)


@override_settings(
    INVOICE_SELLER_NAME="Aman Trading", INVOICE_SELLER_ADDRESS="Kuala Lumpur"
)
class VoidAndCreditDoNotOverlapTests(TestCase):
    """The two ways of undoing a Sale must not double-return the stock."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="overlap-owner", password="test-password-123"
        )

    def setUp(self):
        self.product = Product.objects.create(
            sku="CN-OVERLAP",
            name="Overlap Product",
            selling_price=Decimal("30.00"),
            cost_price=Decimal("10.00"),
            current_stock=10,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            created_by=self.user,
        )

    def test_an_invoiced_sale_is_credited_rather_than_voided(self):
        issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        with self.assertRaisesMessage(SalesOperationError, "credit note"):
            void_sale(
                sale_id=self.sale.pk, reason="Mistake", voided_by=self.user
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 8)

    def test_a_voided_sale_can_never_reach_the_credit_note_route(self):
        void_sale(sale_id=self.sale.pk, reason="Mistake", voided_by=self.user)

        with self.assertRaisesMessage(InvoiceOperationError, "was voided"):
            issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        self.assertFalse(Invoice.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)

    def test_a_sale_counts_once_and_is_cancelled_once(self):
        invoice = issue_invoice(sale_id=self.sale.pk, issued_by=self.user)
        issue_credit_note(
            invoice_id=invoice.pk, reason="Returned", issued_by=self.user
        )

        self.sale.refresh_from_db()
        self.assertTrue(self.sale.is_credited)
        self.assertFalse(self.sale.is_voided)
        self.assertTrue(self.sale.is_cancelled)
        self.assertFalse(Sale.objects.not_cancelled().filter(pk=self.sale.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)
