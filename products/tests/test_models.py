from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from products.models import Product


class ProductModelTests(TestCase):
    def product(self, **overrides):
        values = {
            "sku": "PRD-001",
            "name": "Mechanical Keyboard",
            "selling_price": Decimal("199.90"),
            "cost_price": Decimal("120.00"),
            "current_stock": 8,
            "low_stock_threshold": 3,
        }
        values.update(overrides)
        return Product(**values)

    def test_valid_product_passes_validation_and_saves(self):
        product = self.product()

        product.full_clean()
        product.save()

        self.assertIsNotNone(product.pk)
        self.assertEqual(product.selling_price, Decimal("199.90"))

    def test_sku_is_required(self):
        product = self.product(sku="")

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("sku", context.exception.message_dict)

    def test_sku_is_trimmed_and_normalized_to_uppercase(self):
        product = self.product(sku="  prd-abc-9  ")

        product.full_clean()
        product.save()
        product.refresh_from_db()

        self.assertEqual(product.sku, "PRD-ABC-9")

    def test_duplicate_normalized_sku_is_rejected(self):
        self.product(sku="PRD-002").save()
        duplicate = self.product(sku=" prd-002 ", name="Duplicate")

        with self.assertRaises(ValidationError) as context:
            duplicate.full_clean()

        self.assertIn("sku", context.exception.message_dict)

    def test_negative_selling_price_is_rejected(self):
        product = self.product(selling_price=Decimal("-0.01"))

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("selling_price", context.exception.message_dict)

    def test_negative_cost_price_is_rejected(self):
        product = self.product(cost_price=Decimal("-0.01"))

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("cost_price", context.exception.message_dict)

    def test_negative_current_stock_is_rejected(self):
        product = self.product(current_stock=-1)

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("current_stock", context.exception.message_dict)

    def test_negative_low_stock_threshold_is_rejected(self):
        product = self.product(low_stock_threshold=-1)

        with self.assertRaises(ValidationError) as context:
            product.full_clean()

        self.assertIn("low_stock_threshold", context.exception.message_dict)

    def test_database_rejects_negative_selling_price(self):
        product = self.product()
        product.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(selling_price=-1)

    def test_database_rejects_negative_cost_price(self):
        product = self.product()
        product.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(cost_price=-1)

    def test_database_rejects_negative_current_stock(self):
        product = self.product()
        product.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(current_stock=-1)

    def test_database_rejects_negative_threshold(self):
        product = self.product()
        product.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(low_stock_threshold=-1)

    def test_database_rejects_non_uppercase_sku(self):
        product = self.product()
        product.save()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(pk=product.pk).update(sku="lowercase-sku")

    def test_positive_stock_at_threshold_is_low_stock(self):
        product = self.product(current_stock=3, low_stock_threshold=3)

        self.assertTrue(product.is_low_stock)
        self.assertFalse(product.is_out_of_stock)

    def test_positive_stock_below_threshold_is_low_stock(self):
        product = self.product(current_stock=2, low_stock_threshold=3)

        self.assertTrue(product.is_low_stock)

    def test_stock_above_threshold_is_not_low_stock(self):
        product = self.product(current_stock=4, low_stock_threshold=3)

        self.assertFalse(product.is_low_stock)

    def test_zero_stock_is_out_of_stock_not_low_stock(self):
        product = self.product(current_stock=0, low_stock_threshold=3)

        self.assertTrue(product.is_out_of_stock)
        self.assertFalse(product.is_low_stock)

    def test_inactive_product_is_not_low_or_out_of_stock(self):
        product = self.product(is_active=False, current_stock=1, low_stock_threshold=3)

        self.assertFalse(product.is_low_stock)
        self.assertFalse(product.is_out_of_stock)

    def test_deactivation_preserves_product_row(self):
        product = self.product()
        product.save()

        product.is_active = False
        product.save(update_fields=["is_active", "updated_at"])

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(Product.objects.get(pk=product.pk).is_active)
