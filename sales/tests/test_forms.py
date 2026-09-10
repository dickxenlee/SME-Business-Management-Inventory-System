from decimal import Decimal

from django.test import TestCase

from customers.models import Customer
from products.models import Product
from sales.forms import SaleForm, SaleItemForm, SaleItemFormSet


class SaleFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.active_customer = Customer.objects.create(name="Active Customer")
        cls.inactive_customer = Customer.objects.create(
            name="Inactive Customer",
            is_active=False,
        )
        cls.active_product = Product.objects.create(
            sku="FORM-1",
            name="Active Product",
            selling_price=Decimal("15.00"),
            cost_price=Decimal("8.00"),
            current_stock=5,
        )
        cls.inactive_product = Product.objects.create(
            sku="FORM-2",
            name="Inactive Product",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("10.00"),
            current_stock=5,
            is_active=False,
        )

    def formset_data(self, rows):
        data = {
            "items-TOTAL_FORMS": str(len(rows)),
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            for name, value in row.items():
                data[f"items-{index}-{name}"] = value
        return data

    def test_walk_in_customer_is_allowed(self):
        form = SaleForm(data={"customer": ""})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["customer"])

    def test_only_active_customers_are_selectable(self):
        form = SaleForm()

        self.assertIn(self.active_customer, form.fields["customer"].queryset)
        self.assertNotIn(self.inactive_customer, form.fields["customer"].queryset)

    def test_inactive_customer_submission_is_rejected(self):
        form = SaleForm(data={"customer": self.inactive_customer.pk})

        self.assertFalse(form.is_valid())
        self.assertIn("customer", form.errors)

    def test_item_form_exposes_no_price_field(self):
        form = SaleItemForm()

        self.assertEqual(set(form.fields), {"product", "quantity"})

    def test_product_choices_include_current_price_and_stock(self):
        form = SaleItemForm()
        choices = dict(form.fields["product"].choices)

        self.assertIn("RM 15.00", choices[self.active_product.pk])
        self.assertIn("Stock: 5", choices[self.active_product.pk])

    def test_only_active_products_are_selectable(self):
        form = SaleItemForm()

        self.assertIn(self.active_product, form.fields["product"].queryset)
        self.assertNotIn(self.inactive_product, form.fields["product"].queryset)

    def test_quantity_must_be_positive(self):
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                form = SaleItemForm(
                    data={"product": self.active_product.pk, "quantity": quantity}
                )
                self.assertFalse(form.is_valid())
                self.assertIn("quantity", form.errors)

    def test_formset_requires_at_least_one_item(self):
        formset = SaleItemFormSet(
            data=self.formset_data([{"product": "", "quantity": ""}]),
            prefix="items",
        )

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())

    def test_formset_rejects_duplicate_products(self):
        formset = SaleItemFormSet(
            data=self.formset_data(
                [
                    {"product": self.active_product.pk, "quantity": 1},
                    {"product": self.active_product.pk, "quantity": 2},
                ]
            ),
            prefix="items",
        )

        self.assertFalse(formset.is_valid())
        self.assertIn("once", str(formset.non_form_errors()))

    def test_valid_multiple_item_formset_returns_products_and_quantities(self):
        second_product = Product.objects.create(
            sku="FORM-3",
            name="Second Product",
            selling_price=Decimal("5.00"),
            cost_price=Decimal("2.00"),
            current_stock=2,
        )
        formset = SaleItemFormSet(
            data=self.formset_data(
                [
                    {"product": self.active_product.pk, "quantity": 2},
                    {"product": second_product.pk, "quantity": 1},
                ]
            ),
            prefix="items",
        )

        self.assertTrue(formset.is_valid(), formset.errors)
        cleaned = [form.cleaned_data for form in formset.forms]
        self.assertEqual(cleaned[0]["product"], self.active_product)
        self.assertEqual(cleaned[0]["quantity"], 2)
        self.assertEqual(cleaned[1]["product"], second_product)


class SaleItemDeletionStateTests(TestCase):
    """Regression cover for line items silently dropped after a re-render."""

    @classmethod
    def setUpTestData(cls):
        cls.alpha = Product.objects.create(
            sku="DEL-1",
            name="Alpha",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            current_stock=100,
        )
        cls.bravo = Product.objects.create(
            sku="DEL-2",
            name="Bravo",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("9.00"),
            current_stock=100,
        )

    def formset_data(self, rows):
        data = {
            "items-TOTAL_FORMS": str(len(rows)),
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            for name, value in row.items():
                data[f"items-{index}-{name}"] = value
        return data

    def test_deletion_checkbox_is_rendered_visibly(self):
        formset = SaleItemFormSet(prefix="items")
        rendered = str(formset.forms[0]["DELETE"])

        self.assertIn("form-check-input", rendered)
        self.assertNotIn("type=\"hidden\"", rendered)

    def test_deletion_checkbox_keeps_its_checked_state_for_re_render(self):
        formset = SaleItemFormSet(
            self.formset_data(
                [
                    {"product": self.alpha.pk, "quantity": "2"},
                    {"product": self.bravo.pk, "quantity": "5", "DELETE": "on"},
                ]
            ),
            prefix="items",
        )
        self.assertTrue(formset.is_valid(), formset.errors)

        # The template derives the removed styling from this checkbox, so the
        # state has to survive a bound re-render for the two to stay in sync.
        self.assertIn("checked", str(formset.forms[1]["DELETE"]))
        self.assertNotIn("checked", str(formset.forms[0]["DELETE"]))

    def test_duplicate_products_are_rejected_despite_a_broken_deleted_row(self):
        formset = SaleItemFormSet(
            self.formset_data(
                [
                    {"product": self.alpha.pk, "quantity": "2"},
                    {"product": self.alpha.pk, "quantity": "3"},
                    {"product": self.bravo.pk, "quantity": "oops", "DELETE": "on"},
                ]
            ),
            prefix="items",
        )

        self.assertFalse(formset.is_valid())
        self.assertIn(
            "Each product may appear only once in a Sale.",
            formset.non_form_errors(),
        )

    def test_errors_on_a_deleted_row_do_not_suppress_the_empty_sale_check(self):
        formset = SaleItemFormSet(
            self.formset_data(
                [{"product": self.alpha.pk, "quantity": "nope", "DELETE": "on"}]
            ),
            prefix="items",
        )

        self.assertFalse(formset.is_valid())
        self.assertTrue(formset.non_form_errors())
