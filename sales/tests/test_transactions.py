from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase

from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale, SaleItem
from sales.services import SalesOperationError, create_sale


class SaleTransactionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="sale-rollback-user")

    def setUp(self):
        self.product_a = Product.objects.create(
            sku="ROLLBACK-A",
            name="Rollback A",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("4.00"),
            current_stock=5,
        )
        self.product_b = Product.objects.create(
            sku="ROLLBACK-B",
            name="Rollback B",
            selling_price=Decimal("8.00"),
            cost_price=Decimal("3.00"),
            current_stock=2,
        )

    def assert_database_unchanged(self):
        self.product_a.refresh_from_db()
        self.product_b.refresh_from_db()
        self.assertEqual(self.product_a.current_stock, 5)
        self.assertEqual(self.product_b.current_stock, 2)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_insufficient_last_product_rejects_complete_sale(self):
        with self.assertRaisesMessage(SalesOperationError, "Only 2 left of Rollback B"):
            create_sale(
                customer_id=None,
                items=[
                    {"product_id": self.product_a.pk, "quantity": 2},
                    {"product_id": self.product_b.pk, "quantity": 3},
                ],
                created_by=self.user,
            )

        self.assert_database_unchanged()

    def test_sale_item_write_failure_rolls_back_prior_stock_and_movement(self):
        original_create = SaleItem.objects.create
        calls = 0

        def fail_on_second_item(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise DatabaseError("item write failed")
            return original_create(**kwargs)

        with patch.object(SaleItem.objects, "create", side_effect=fail_on_second_item):
            with self.assertRaisesMessage(DatabaseError, "item write failed"):
                create_sale(
                    customer_id=None,
                    items=[
                        {"product_id": self.product_a.pk, "quantity": 2},
                        {"product_id": self.product_b.pk, "quantity": 1},
                    ],
                    created_by=self.user,
                )

        self.assert_database_unchanged()

    def test_total_above_decimal_field_capacity_is_rejected_cleanly(self):
        products = Product.objects.bulk_create(
            [
                Product(
                    sku=f"OVERFLOW-{number:03d}",
                    name=f"Overflow Product {number:03d}",
                    selling_price=Decimal("9999999999.99"),
                    cost_price=Decimal("0.00"),
                    current_stock=2_147_483_647,
                )
                for number in range(466)
            ]
        )

        with self.assertRaisesMessage(
            SalesOperationError,
            "Sale total exceeds the supported maximum",
        ):
            create_sale(
                customer_id=None,
                items=[
                    {"product_id": product.pk, "quantity": 2_147_483_647}
                    for product in products
                ],
                created_by=self.user,
            )

        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(SaleItem.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertFalse(
            Product.objects.filter(pk__in=[product.pk for product in products])
            .exclude(current_stock=2_147_483_647)
            .exists()
        )
