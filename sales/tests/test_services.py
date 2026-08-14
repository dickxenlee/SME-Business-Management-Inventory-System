from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Customer
from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale, SaleItem
from sales.services import SalesOperationError, create_sale


class CreateSaleServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="sale-creator")
        cls.customer = Customer.objects.create(
            name="Original Customer",
            address="Original Address",
        )

    def setUp(self):
        self.product_a = Product.objects.create(
            sku="SERVICE-A",
            name="Service Product A",
            selling_price=Decimal("12.50"),
            cost_price=Decimal("6.00"),
            current_stock=10,
        )
        self.product_b = Product.objects.create(
            sku="SERVICE-B",
            name="Service Product B",
            selling_price=Decimal("5.25"),
            cost_price=Decimal("2.00"),
            current_stock=8,
        )

    def test_one_item_sale_records_snapshots_total_stock_and_movement(self):
        sale = create_sale(
            customer_id=self.customer.pk,
            items=[{"product_id": self.product_a.pk, "quantity": 2}],
            created_by=self.user,
        )

        self.product_a.refresh_from_db()
        item = sale.items.select_related("stock_movement").get()
        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.customer_name, "Original Customer")
        self.assertEqual(sale.customer_address, "Original Address")
        self.assertEqual(sale.total_amount, Decimal("25.00"))
        self.assertEqual(sale.created_by, self.user)
        self.assertEqual(item.product_sku, "SERVICE-A")
        self.assertEqual(item.product_name, "Service Product A")
        self.assertEqual(item.unit_price, Decimal("12.50"))
        self.assertEqual(item.subtotal, Decimal("25.00"))
        self.assertEqual(self.product_a.current_stock, 8)
        self.assertEqual(item.stock_movement.previous_stock, 10)
        self.assertEqual(item.stock_movement.new_stock, 8)
        self.assertEqual(item.stock_movement.quantity, 2)
        self.assertEqual(item.stock_movement.reason, f"Sale {sale.sale_number}")
        self.assertEqual(item.stock_movement.performed_by, self.user)

    def test_multiple_items_calculate_one_total_and_one_movement_each(self):
        sale = create_sale(
            customer_id=self.customer.pk,
            items=[
                {"product_id": self.product_b.pk, "quantity": 3},
                {"product_id": self.product_a.pk, "quantity": 2},
            ],
            created_by=self.user,
        )

        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(sale.total_amount, Decimal("40.75"))
        self.assertEqual(sale.items.count(), 2)
        self.assertEqual(StockMovement.objects.count(), 2)
        self.assertEqual(self.product_a.current_stock, 8)
        self.assertEqual(self.product_b.current_stock, 5)
        self.assertEqual(
            list(sale.items.values_list("product_id", flat=True)),
            sorted((self.product_a.pk, self.product_b.pk)),
        )

    def test_walk_in_sale_has_no_customer_or_customer_snapshots(self):
        sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product_a.pk, "quantity": 1}],
            created_by=self.user,
        )

        self.assertIsNone(sale.customer)
        self.assertEqual(sale.customer_name, "")
        self.assertEqual(sale.customer_address, "")

    def assert_rejected_without_changes(self, operation, message):
        with self.assertRaisesMessage(SalesOperationError, message):
            operation()

        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.current_stock, 10)
        self.assertEqual(self.product_b.current_stock, 8)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_inactive_customer_is_rejected(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active", "updated_at"])

        self.assert_rejected_without_changes(
            lambda: create_sale(
                customer_id=self.customer.pk,
                items=[{"product_id": self.product_a.pk, "quantity": 1}],
                created_by=self.user,
            ),
            "Customer is not available",
        )

    def test_missing_customer_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: create_sale(
                customer_id=999999,
                items=[{"product_id": self.product_a.pk, "quantity": 1}],
                created_by=self.user,
            ),
            "Customer is not available",
        )

    def test_inactive_product_is_rejected(self):
        self.product_a.is_active = False
        self.product_a.save(update_fields=["is_active", "updated_at"])

        self.assert_rejected_without_changes(
            lambda: create_sale(
                customer_id=None,
                items=[{"product_id": self.product_a.pk, "quantity": 1}],
                created_by=self.user,
            ),
            "Product is not available",
        )

    def test_missing_product_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: create_sale(
                customer_id=None,
                items=[{"product_id": 999999, "quantity": 1}],
                created_by=self.user,
            ),
            "Product is not available",
        )

    def test_duplicate_product_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: create_sale(
                customer_id=None,
                items=[
                    {"product_id": self.product_a.pk, "quantity": 1},
                    {"product_id": self.product_a.pk, "quantity": 2},
                ],
                created_by=self.user,
            ),
            "Each product may appear only once",
        )

    def test_empty_items_and_invalid_quantities_are_rejected(self):
        operations = (
            (
                lambda: create_sale(
                    customer_id=None,
                    items=[],
                    created_by=self.user,
                ),
                "Add at least one Sale item",
            ),
            (
                lambda: create_sale(
                    customer_id=None,
                    items=[{"product_id": self.product_a.pk, "quantity": 0}],
                    created_by=self.user,
                ),
                "Quantity must be a positive whole number",
            ),
        )

        for operation, message in operations:
            with self.subTest(message=message):
                self.assert_rejected_without_changes(operation, message)
