from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import StockMovement
from inventory.services import (
    InventoryOperationError,
    MAX_STOCK_QUANTITY,
    adjust_stock,
    stock_in,
    stock_out,
)
from products.models import Product


class InventoryServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="operator")

    def setUp(self):
        self.product = Product.objects.create(
            sku="SERVICE-1",
            name="Service Product",
            selling_price=20,
            cost_price=10,
            current_stock=10,
        )

    def test_stock_in_updates_product_and_creates_one_movement(self):
        movement = stock_in(
            product_id=self.product.pk,
            quantity=4,
            performed_by=self.user,
            reason="Supplier delivery",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 14)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.STOCK_IN)
        self.assertEqual(movement.quantity, 4)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 14)
        self.assertEqual(movement.performed_by, self.user)
        self.assertEqual(movement.reason, "Supplier delivery")
        self.assertIsNotNone(movement.created_at)

    def test_stock_out_updates_product_and_creates_one_movement(self):
        movement = stock_out(
            product_id=self.product.pk,
            quantity=3,
            performed_by=self.user,
            reason="Damaged unit",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 7)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.STOCK_OUT)
        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 7)

    def test_adjustment_uses_final_stock_and_positive_difference(self):
        movement = adjust_stock(
            product_id=self.product.pk,
            new_stock=6,
            performed_by=self.user,
            reason="Physical count correction",
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 6)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.ADJUSTMENT)
        self.assertEqual(movement.quantity, 4)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 6)

    def test_adjustment_can_increase_to_final_stock(self):
        movement = adjust_stock(
            product_id=self.product.pk,
            new_stock=13,
            performed_by=self.user,
            reason="Physical count correction",
        )

        self.assertEqual(movement.quantity, 3)
        self.assertEqual(movement.previous_stock, 10)
        self.assertEqual(movement.new_stock, 13)

    def assert_rejected_without_changes(self, operation, message):
        with self.assertRaisesMessage(InventoryOperationError, message):
            operation()

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_stock_out_beyond_available_stock_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: stock_out(
                product_id=self.product.pk,
                quantity=11,
                performed_by=self.user,
            ),
            "Insufficient stock",
        )

    def test_inactive_product_rejects_every_operation(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active", "updated_at"])

        operations = (
            lambda: stock_in(
                product_id=self.product.pk,
                quantity=1,
                performed_by=self.user,
            ),
            lambda: stock_out(
                product_id=self.product.pk,
                quantity=1,
                performed_by=self.user,
            ),
            lambda: adjust_stock(
                product_id=self.product.pk,
                new_stock=1,
                performed_by=self.user,
                reason="Count",
            ),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesMessage(
                    InventoryOperationError,
                    "Inactive products cannot receive stock movements",
                ):
                    operation()

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 10)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_zero_and_negative_quantities_are_rejected(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                self.assert_rejected_without_changes(
                    lambda: stock_in(
                        product_id=self.product.pk,
                        quantity=quantity,
                        performed_by=self.user,
                    ),
                    "Quantity must be a positive whole number",
                )

    def test_stock_out_rejects_zero_and_negative_quantities(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                self.assert_rejected_without_changes(
                    lambda: stock_out(
                        product_id=self.product.pk,
                        quantity=quantity,
                        performed_by=self.user,
                    ),
                    "Quantity must be a positive whole number",
                )

    def test_stock_in_rejects_a_result_above_database_maximum(self):
        self.product.current_stock = MAX_STOCK_QUANTITY
        self.product.save(update_fields=["current_stock", "updated_at"])

        with self.assertRaisesMessage(
            InventoryOperationError,
            "Resulting stock exceeds the supported maximum",
        ):
            stock_in(
                product_id=self.product.pk,
                quantity=1,
                performed_by=self.user,
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, MAX_STOCK_QUANTITY)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_stock_out_rejects_quantity_above_database_maximum(self):
        self.assert_rejected_without_changes(
            lambda: stock_out(
                product_id=self.product.pk,
                quantity=MAX_STOCK_QUANTITY + 1,
                performed_by=self.user,
            ),
            "Quantity exceeds the supported maximum",
        )

    def test_adjustment_rejects_target_above_database_maximum(self):
        self.assert_rejected_without_changes(
            lambda: adjust_stock(
                product_id=self.product.pk,
                new_stock=MAX_STOCK_QUANTITY + 1,
                performed_by=self.user,
                reason="Count",
            ),
            "Final stock exceeds the supported maximum",
        )

    def test_negative_adjustment_target_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: adjust_stock(
                product_id=self.product.pk,
                new_stock=-1,
                performed_by=self.user,
                reason="Count",
            ),
            "Final stock must be a non-negative whole number",
        )

    def test_no_op_adjustment_is_rejected(self):
        self.assert_rejected_without_changes(
            lambda: adjust_stock(
                product_id=self.product.pk,
                new_stock=10,
                performed_by=self.user,
                reason="Count",
            ),
            "Adjustment must change the stock level",
        )

    def test_adjustment_requires_a_nonblank_reason(self):
        self.assert_rejected_without_changes(
            lambda: adjust_stock(
                product_id=self.product.pk,
                new_stock=8,
                performed_by=self.user,
                reason="  ",
            ),
            "A reason is required for stock adjustments",
        )
