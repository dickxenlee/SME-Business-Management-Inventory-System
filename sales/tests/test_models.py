from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from customers.models import Customer
from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale, SaleItem


class SaleModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="sales-model-user")
        cls.customer = Customer.objects.create(
            name="Acme Trading",
            address="Kuala Lumpur",
        )
        cls.product = Product.objects.create(
            sku="SALE-MODEL-1",
            name="Sales Model Product",
            selling_price=Decimal("12.50"),
            cost_price=Decimal("8.00"),
            current_stock=10,
        )

    def create_sale(self, **overrides):
        values = {
            "customer": self.customer,
            "customer_name": "Acme Trading",
            "customer_address": "Kuala Lumpur",
            "total_amount": Decimal("25.00"),
            "created_by": self.user,
        }
        values.update(overrides)
        return Sale.objects.create(**values)

    def create_item(self, sale, **overrides):
        movement = overrides.pop("stock_movement", None)
        if movement is None:
            movement = StockMovement.objects.create(
                product=self.product,
                movement_type=StockMovement.MovementType.STOCK_OUT,
                quantity=2,
                previous_stock=10,
                new_stock=8,
                reason="Sale",
                performed_by=self.user,
            )
        values = {
            "sale": sale,
            "product": self.product,
            "stock_movement": movement,
            "product_sku": "SALE-MODEL-1",
            "product_name": "Sales Model Product",
            "quantity": 2,
            "unit_price": Decimal("12.50"),
            "subtotal": Decimal("25.00"),
        }
        values.update(overrides)
        return SaleItem.objects.create(**values)

    def test_sale_stores_customer_snapshot_creator_total_and_timestamp(self):
        sale = self.create_sale()

        self.assertEqual(sale.customer, self.customer)
        self.assertEqual(sale.customer_name, "Acme Trading")
        self.assertEqual(sale.customer_address, "Kuala Lumpur")
        self.assertEqual(sale.total_amount, Decimal("25.00"))
        self.assertEqual(sale.created_by, self.user)
        self.assertIsNotNone(sale.created_at)

    def test_sale_number_is_derived_from_primary_key(self):
        sale = self.create_sale()

        self.assertEqual(sale.sale_number, f"SALE-{sale.pk:06d}")
        self.assertEqual(str(sale), sale.sale_number)

    def test_walk_in_sale_allows_no_customer_and_blank_snapshots(self):
        sale = self.create_sale(
            customer=None,
            customer_name="",
            customer_address="",
        )

        self.assertIsNone(sale.customer)
        self.assertEqual(sale.customer_name, "")
        self.assertEqual(sale.customer_address, "")

    def test_sale_item_stores_product_price_and_movement_snapshots(self):
        sale = self.create_sale()
        item = self.create_item(sale)

        self.assertEqual(item.product, self.product)
        self.assertEqual(item.product_sku, "SALE-MODEL-1")
        self.assertEqual(item.product_name, "Sales Model Product")
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, Decimal("12.50"))
        self.assertEqual(item.subtotal, Decimal("25.00"))
        self.assertEqual(item.stock_movement.product, self.product)
        self.assertEqual(sale.items.get(), item)

    def test_sale_deletion_cascades_owned_items(self):
        sale = self.create_sale()
        self.create_item(sale)

        sale.delete()

        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_customer_product_and_stock_movement_deletion_are_protected(self):
        sale = self.create_sale()
        item = self.create_item(sale)

        for instance in (self.customer, self.product, item.stock_movement):
            with self.subTest(model=type(instance).__name__):
                with self.assertRaises(ProtectedError):
                    instance.delete()

    def test_creator_deletion_preserves_sale(self):
        sale = self.create_sale()

        self.user.delete()
        sale.refresh_from_db()

        self.assertIsNone(sale.created_by)

    def test_database_rejects_negative_sale_total(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_sale(total_amount=Decimal("-0.01"))

    def test_database_rejects_nonpositive_item_quantity(self):
        sale = self.create_sale()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_item(sale, quantity=0)

    def test_database_rejects_negative_item_money(self):
        for field in ("unit_price", "subtotal"):
            with self.subTest(field=field):
                sale = self.create_sale()
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.create_item(sale, **{field: Decimal("-0.01")})

    def test_product_can_appear_only_once_per_sale(self):
        sale = self.create_sale()
        self.create_item(sale)
        second_movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.STOCK_OUT,
            quantity=1,
            previous_stock=8,
            new_stock=7,
            performed_by=self.user,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_item(sale, stock_movement=second_movement, quantity=1)

    def test_stock_movement_can_belong_to_only_one_sale_item(self):
        first_sale = self.create_sale()
        movement = self.create_item(first_sale).stock_movement
        second_sale = self.create_sale()

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_item(second_sale, stock_movement=movement)
