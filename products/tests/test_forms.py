from decimal import Decimal

from django.test import TestCase

from products.forms import ProductForm
from products.models import Product


class ProductFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "sku": " prd-100 ",
            "name": "USB-C Dock",
            "selling_price": "299.90",
            "cost_price": "210.00",
            "current_stock": "5",
            "low_stock_threshold": "2",
        }
        data.update(overrides)
        return data

    def test_valid_form_normalizes_and_saves_product(self):
        form = ProductForm(data=self.valid_data())

        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()

        self.assertEqual(product.sku, "PRD-100")
        self.assertEqual(product.selling_price, Decimal("299.90"))

    def test_duplicate_sku_with_different_case_is_rejected(self):
        Product.objects.create(
            sku="PRD-100",
            name="Existing",
            selling_price=10,
            cost_price=5,
        )

        form = ProductForm(data=self.valid_data(sku="prd-100"))

        self.assertFalse(form.is_valid())
        self.assertIn("sku", form.errors)

    def test_negative_values_are_rejected_without_saving(self):
        fields = (
            "selling_price",
            "cost_price",
            "current_stock",
            "low_stock_threshold",
        )

        for field in fields:
            with self.subTest(field=field):
                form = ProductForm(data=self.valid_data(**{field: "-1"}))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

        self.assertEqual(Product.objects.count(), 0)

    def test_invalid_form_preserves_entered_values(self):
        form = ProductForm(data=self.valid_data(name="Entered name", selling_price="-1"))

        self.assertFalse(form.is_valid())

        self.assertEqual(form["name"].value(), "Entered name")

    def test_active_status_is_not_exposed_by_product_form(self):
        form = ProductForm()

        self.assertNotIn("is_active", form.fields)

