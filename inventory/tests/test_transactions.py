from unittest.mock import patch
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections
from django.test import TestCase, TransactionTestCase

from inventory.models import StockMovement
from inventory.services import stock_in
from products.models import Product


class InventoryRollbackTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="rollback-user")

    def setUp(self):
        self.product = Product.objects.create(
            sku="ROLLBACK-1",
            name="Rollback Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
        )

    def test_movement_creation_failure_rolls_back_product_update(self):
        with patch.object(
            StockMovement.objects,
            "create",
            side_effect=DatabaseError("movement write failed"),
        ):
            with self.assertRaises(DatabaseError):
                stock_in(
                    product_id=self.product.pk,
                    quantity=2,
                    performed_by=self.user,
                )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 5)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_product_update_failure_leaves_no_movement(self):
        with patch.object(
            Product,
            "save",
            side_effect=DatabaseError("product write failed"),
        ):
            with self.assertRaises(DatabaseError):
                stock_in(
                    product_id=self.product.pk,
                    quantity=2,
                    performed_by=self.user,
                )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 5)
        self.assertEqual(StockMovement.objects.count(), 0)


class InventoryConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="concurrent-user")
        self.product = Product.objects.create(
            sku="CONCURRENT-1",
            name="Concurrent Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
        )

    def test_concurrent_updates_use_the_latest_locked_stock(self):
        barrier = Barrier(3)
        errors = []

        def add_stock(quantity):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                stock_in(
                    product_id=self.product.pk,
                    quantity=quantity,
                    performed_by=self.user,
                )
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [Thread(target=add_stock, args=(quantity,)) for quantity in (2, 3)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)

        movements = list(StockMovement.objects.order_by("created_at", "pk"))
        self.assertEqual(len(movements), 2)
        self.assertEqual(movements[0].previous_stock, 5)
        self.assertEqual(movements[0].new_stock, movements[1].previous_stock)
        self.assertEqual(movements[1].new_stock, 10)
        self.assertEqual({movement.quantity for movement in movements}, {2, 3})
