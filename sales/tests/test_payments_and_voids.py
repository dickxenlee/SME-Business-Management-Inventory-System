from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from inventory.models import StockMovement
from products.models import Product
from reports.services import get_sales_report, resolve_period
from sales.models import PaymentMethod, SaleReversal
from sales.services import SalesOperationError, create_sale, void_sale


class PaymentCaptureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="pay-user")

    def setUp(self):
        self.product = Product.objects.create(
            sku="PAY-1",
            name="Paid Product",
            selling_price=Decimal("30.00"),
            cost_price=Decimal("10.00"),
            current_stock=20,
        )

    def sell(self, **kwargs):
        return create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            created_by=self.user,
            **kwargs,
        )

    def test_cash_records_tendered_and_works_out_change(self):
        sale = self.sell(
            payment_method=PaymentMethod.CASH, amount_tendered=Decimal("100.00")
        )

        self.assertEqual(sale.total_amount, Decimal("60.00"))
        self.assertEqual(sale.amount_tendered, Decimal("100.00"))
        self.assertEqual(sale.change_given, Decimal("40.00"))

    def test_exact_cash_gives_no_change(self):
        sale = self.sell(
            payment_method=PaymentMethod.CASH, amount_tendered=Decimal("60.00")
        )

        self.assertEqual(sale.change_given, Decimal("0.00"))

    def test_cash_short_of_the_total_is_rejected(self):
        with self.assertRaisesMessage(SalesOperationError, "does not cover"):
            self.sell(
                payment_method=PaymentMethod.CASH,
                amount_tendered=Decimal("59.99"),
            )

    def test_card_takes_the_exact_amount_and_records_no_cash_movement(self):
        """A tendered figure on a card sale would invent a drawer movement."""
        sale = self.sell(
            payment_method=PaymentMethod.CARD, amount_tendered=Decimal("100.00")
        )

        self.assertEqual(sale.payment_method, PaymentMethod.CARD)
        self.assertIsNone(sale.amount_tendered)
        self.assertIsNone(sale.change_given)

    def test_unknown_payment_method_is_rejected(self):
        with self.assertRaisesMessage(SalesOperationError, "Unknown payment method"):
            self.sell(payment_method="CRYPTO")

    def test_payment_may_be_left_unrecorded(self):
        sale = self.sell()

        self.assertEqual(sale.payment_method, "")
        self.assertIsNone(sale.amount_tendered)


class VoidSaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="void-user")

    def setUp(self):
        self.product = Product.objects.create(
            sku="VOID-1",
            name="Voidable Product",
            selling_price=Decimal("25.00"),
            cost_price=Decimal("10.00"),
            current_stock=10,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 3}],
            created_by=self.user,
        )

    def test_voiding_returns_the_stock(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 7)

        void_sale(sale_id=self.sale.pk, reason="Rang up twice", voided_by=self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)
        returned = StockMovement.objects.filter(
            movement_type=StockMovement.MovementType.STOCK_IN,
            reason="Void of " + self.sale.sale_number,
        )
        self.assertEqual(returned.count(), 1)
        self.assertEqual(returned.get().quantity, 3)

    def test_the_sale_itself_is_never_edited_or_deleted(self):
        """Immutability is the point: the record of what was rung up survives,
        and the void is a separate later record."""
        before = (
            self.sale.total_amount,
            self.sale.net_amount,
            self.sale.items.count(),
        )

        void_sale(sale_id=self.sale.pk, reason="Wrong customer", voided_by=self.user)

        self.sale.refresh_from_db()
        self.assertEqual(
            (self.sale.total_amount, self.sale.net_amount, self.sale.items.count()),
            before,
        )
        self.assertTrue(self.sale.is_voided)
        self.assertEqual(self.sale.reversal.reason, "Wrong customer")

    def test_a_sale_cannot_be_voided_twice(self):
        void_sale(sale_id=self.sale.pk, reason="First", voided_by=self.user)

        with self.assertRaisesMessage(SalesOperationError, "already been voided"):
            void_sale(sale_id=self.sale.pk, reason="Second", voided_by=self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)

    def test_a_reason_is_required(self):
        with self.assertRaisesMessage(SalesOperationError, "reason is required"):
            void_sale(sale_id=self.sale.pk, reason="   ", voided_by=self.user)

        self.assertFalse(SaleReversal.objects.exists())

    def test_an_invoiced_sale_needs_a_credit_note_not_a_void(self):
        from invoices.services import issue_invoice

        with override_settings(
            INVOICE_SELLER_NAME="Seller", INVOICE_SELLER_ADDRESS="Address"
        ):
            issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        with self.assertRaisesMessage(SalesOperationError, "credit note"):
            void_sale(sale_id=self.sale.pk, reason="Mistake", voided_by=self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 7)

    def test_stock_comes_back_even_if_the_product_was_deactivated(self):
        """Otherwise a deactivated line makes the void impossible and leaves
        the stock count permanently wrong."""
        self.product.is_active = False
        self.product.save(update_fields=["is_active", "updated_at"])

        void_sale(sale_id=self.sale.pk, reason="Discontinued", voided_by=self.user)

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class VoidedSalesLeaveRevenueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="void-report")

    def test_a_voided_sale_stops_counting_towards_revenue_and_margin(self):
        product = Product.objects.create(
            sku="VOID-REP",
            name="Void Report Product",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            current_stock=10,
        )
        kept = create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=self.user,
        )
        scrapped = create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=self.user,
        )

        before = get_sales_report(resolve_period("30d"))
        self.assertEqual(before["revenue"], Decimal("200.00"))
        self.assertEqual(before["sale_count"], 2)

        void_sale(sale_id=scrapped.pk, reason="Keyed twice", voided_by=self.user)

        after = get_sales_report(resolve_period("30d"))
        self.assertEqual(after["revenue"], Decimal("100.00"))
        self.assertEqual(after["sale_count"], 1)
        self.assertEqual(after["margin"]["gross_profit"], Decimal("40.00"))
        self.assertEqual([sale.pk for sale in after["recent_sales"]], [kept.pk])


class VoidedSaleCannotBeInvoicedTests(TestCase):
    """A voided Sale's goods went back, so it must not produce a document."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username="void-invoice", password="test-password-123"
        )

    def setUp(self):
        self.product = Product.objects.create(
            sku="VOID-INV",
            name="Void Invoice Product",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("8.00"),
            current_stock=10,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            created_by=self.user,
        )
        void_sale(sale_id=self.sale.pk, reason="Keyed twice", voided_by=self.user)

    @override_settings(
        INVOICE_SELLER_NAME="Seller", INVOICE_SELLER_ADDRESS="Address"
    )
    def test_the_service_refuses_to_invoice_a_voided_sale(self):
        from invoices.models import Invoice
        from invoices.services import InvoiceOperationError, issue_invoice

        with self.assertRaisesMessage(InvoiceOperationError, "was voided"):
            issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        self.assertFalse(Invoice.objects.exists())

    def test_the_detail_page_does_not_offer_to_invoice_a_voided_sale(self):
        from django.urls import reverse

        self.client.force_login(self.user)
        response = self.client.get(reverse("sales:detail", args=[self.sale.pk]))

        self.assertContains(response, "Voided")
        self.assertNotContains(response, "Issue invoice")
