from decimal import Decimal
from threading import Barrier, Lock, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase

from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale
from sales.services import SalesOperationError, create_sale


class SaleConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="sale-concurrent")

    def run_concurrently(self, item_groups):
        barrier = Barrier(len(item_groups) + 1)
        result_lock = Lock()
        successes = []
        errors = []

        def create(items):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                sale = create_sale(
                    customer_id=None,
                    items=items,
                    created_by=self.user,
                )
                with result_lock:
                    successes.append(sale.pk)
            except Exception as exc:  # pragma: no cover - asserted by caller
                with result_lock:
                    errors.append(exc)
            finally:
                close_old_connections()

        threads = [Thread(target=create, args=(items,)) for items in item_groups]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        return successes, errors

    def product(self, sku, stock):
        return Product.objects.create(
            sku=sku,
            name=sku,
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            current_stock=stock,
        )

    def test_concurrent_sales_cannot_oversell_limited_stock(self):
        product = self.product("CONCURRENT-SALE", 5)

        successes, errors = self.run_concurrently(
            [
                [{"product_id": product.pk, "quantity": 4}],
                [{"product_id": product.pk, "quantity": 4}],
            ]
        )

        product.refresh_from_db()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], SalesOperationError)
        self.assertIn("Insufficient stock", str(errors[0]))
        self.assertEqual(product.current_stock, 1)
        self.assertEqual(Sale.objects.count(), 1)
        movement = StockMovement.objects.get()
        self.assertEqual(movement.previous_stock, 5)
        self.assertEqual(movement.new_stock, 1)

    def test_overlapping_reverse_order_sales_finish_without_deadlock(self):
        product_a = self.product("LOCK-A", 10)
        product_b = self.product("LOCK-B", 10)

        successes, errors = self.run_concurrently(
            [
                [
                    {"product_id": product_a.pk, "quantity": 2},
                    {"product_id": product_b.pk, "quantity": 3},
                ],
                [
                    {"product_id": product_b.pk, "quantity": 4},
                    {"product_id": product_a.pk, "quantity": 1},
                ],
            ]
        )

        product_a.refresh_from_db()
        product_b.refresh_from_db()
        self.assertEqual(len(successes), 2)
        self.assertFalse(errors)
        self.assertEqual(product_a.current_stock, 7)
        self.assertEqual(product_b.current_stock, 3)
        self.assertEqual(Sale.objects.count(), 2)
        self.assertEqual(StockMovement.objects.count(), 4)

        for product, final_stock in ((product_a, 7), (product_b, 3)):
            movements = list(
                StockMovement.objects.filter(product=product).order_by(
                    "created_at", "pk"
                )
            )
            self.assertEqual(movements[0].previous_stock, 10)
            self.assertEqual(movements[0].new_stock, movements[1].previous_stock)
            self.assertEqual(movements[1].new_stock, final_stock)
