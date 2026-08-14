from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from inventory.models import StockMovement
from products.models import Product


class StockMovementModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="stock-user")
        cls.product = Product.objects.create(
            sku="INV-001",
            name="Inventory Product",
            selling_price=20,
            cost_price=10,
        )

    def movement(self, **overrides):
        values = {
            "product": self.product,
            "movement_type": StockMovement.MovementType.STOCK_IN,
            "quantity": 3,
            "previous_stock": 0,
            "new_stock": 3,
            "reason": "Supplier delivery",
            "performed_by": self.user,
        }
        values.update(overrides)
        return StockMovement(**values)

    def test_movement_stores_audit_fields_and_timestamp(self):
        movement = self.movement()
        movement.full_clean()
        movement.save()

        self.assertEqual(movement.product, self.product)
        self.assertEqual(movement.performed_by, self.user)
        self.assertEqual(movement.previous_stock, 0)
        self.assertEqual(movement.new_stock, 3)
        self.assertIsNotNone(movement.created_at)

    def test_supported_movement_types_are_exposed(self):
        self.assertEqual(
            set(StockMovement.MovementType.values),
            {"STOCK_IN", "STOCK_OUT", "ADJUSTMENT"},
        )

    def test_default_ordering_is_newest_first(self):
        first = self.movement(reason="First")
        first.save()
        second = self.movement(reason="Second")
        second.save()

        self.assertEqual(list(StockMovement.objects.all()), [second, first])

    def test_database_rejects_zero_quantity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.movement(quantity=0, new_stock=0).save()

    def test_database_rejects_negative_previous_stock(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.movement(previous_stock=-1).save()

    def test_database_rejects_negative_new_stock(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.movement(new_stock=-1).save()

    def test_product_deletion_is_protected_when_history_exists(self):
        from django.db.models.deletion import ProtectedError

        self.movement().save()

        with self.assertRaises(ProtectedError):
            self.product.delete()

    def test_user_deletion_preserves_history(self):
        movement = self.movement()
        movement.save()

        self.user.delete()
        movement.refresh_from_db()

        self.assertIsNone(movement.performed_by)
