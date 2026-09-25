from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from products.models import Product
from sales.services import SalesOperationError, create_sale


class SaleTaxTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="tax-user")

    def setUp(self):
        self.product = Product.objects.create(
            sku="TAX-1",
            name="Taxed Product",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            current_stock=50,
        )

    def sell(self, quantity=1, discount=None):
        item = {"product_id": self.product.pk, "quantity": quantity}
        if discount is not None:
            item["discount_amount"] = discount
        return create_sale(customer_id=None, items=[item], created_by=self.user)

    @override_settings(SALES_TAX_RATE=Decimal("0"))
    def test_no_tax_is_charged_when_the_rate_is_zero(self):
        sale = self.sell(quantity=2)

        self.assertEqual(sale.net_amount, Decimal("200.00"))
        self.assertEqual(sale.tax_amount, Decimal("0.00"))
        self.assertEqual(sale.total_amount, Decimal("200.00"))

    @override_settings(SALES_TAX_RATE=Decimal("6"))
    def test_tax_is_added_on_top_of_the_net_amount(self):
        sale = self.sell(quantity=2)

        self.assertEqual(sale.net_amount, Decimal("200.00"))
        self.assertEqual(sale.tax_rate, Decimal("6.00"))
        self.assertEqual(sale.tax_amount, Decimal("12.00"))
        self.assertEqual(sale.total_amount, Decimal("212.00"))

    @override_settings(SALES_TAX_RATE=Decimal("6"))
    def test_tax_rate_is_snapshotted_not_looked_up_later(self):
        sale = self.sell(quantity=1)

        with override_settings(SALES_TAX_RATE=Decimal("25")):
            sale.refresh_from_db()
            self.assertEqual(sale.tax_rate, Decimal("6.00"))
            self.assertEqual(sale.tax_amount, Decimal("6.00"))
            self.assertEqual(sale.total_amount, Decimal("106.00"))

    @override_settings(SALES_TAX_RATE=Decimal("6"))
    def test_tax_rounds_to_the_nearest_sen(self):
        self.product.selling_price = Decimal("9.99")
        self.product.save(update_fields=["selling_price", "updated_at"])

        sale = self.sell(quantity=1)

        # 9.99 * 6% = 0.5994 -> 0.60
        self.assertEqual(sale.tax_amount, Decimal("0.60"))
        self.assertEqual(sale.total_amount, Decimal("10.59"))


class SaleDiscountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="discount-user")

    def setUp(self):
        self.product = Product.objects.create(
            sku="DISC-1",
            name="Discounted Product",
            selling_price=Decimal("50.00"),
            cost_price=Decimal("20.00"),
            current_stock=50,
        )

    def sell(self, quantity=1, discount=None):
        item = {"product_id": self.product.pk, "quantity": quantity}
        if discount is not None:
            item["discount_amount"] = discount
        return create_sale(customer_id=None, items=[item], created_by=self.user)

    def test_discount_reduces_the_line_and_the_sale_net(self):
        sale = self.sell(quantity=2, discount=Decimal("15.00"))
        item = sale.items.get()

        self.assertEqual(item.discount_amount, Decimal("15.00"))
        self.assertEqual(item.subtotal, Decimal("85.00"))
        self.assertEqual(sale.net_amount, Decimal("85.00"))

    def test_discount_does_not_change_the_recorded_cost(self):
        """Discounting cuts revenue, not what the stock cost to buy."""
        sale = self.sell(quantity=2, discount=Decimal("15.00"))
        item = sale.items.get()

        self.assertEqual(item.cost_subtotal, Decimal("40.00"))

    def test_a_line_can_be_discounted_to_zero(self):
        sale = self.sell(quantity=1, discount=Decimal("50.00"))

        self.assertEqual(sale.items.get().subtotal, Decimal("0.00"))
        self.assertEqual(sale.net_amount, Decimal("0.00"))

    def test_discount_larger_than_the_line_is_rejected(self):
        with self.assertRaisesMessage(SalesOperationError, "is more than the"):
            self.sell(quantity=1, discount=Decimal("50.01"))

    def test_negative_discount_is_rejected(self):
        with self.assertRaisesMessage(
            SalesOperationError, "Discount cannot be negative"
        ):
            self.sell(quantity=1, discount=Decimal("-1.00"))

    @override_settings(SALES_TAX_RATE=Decimal("6"))
    def test_tax_is_charged_on_the_discounted_amount(self):
        """Tax follows the discount; charging it on the pre-discount price
        would overcharge the customer."""
        sale = self.sell(quantity=2, discount=Decimal("20.00"))

        self.assertEqual(sale.net_amount, Decimal("80.00"))
        self.assertEqual(sale.tax_amount, Decimal("4.80"))
        self.assertEqual(sale.total_amount, Decimal("84.80"))
