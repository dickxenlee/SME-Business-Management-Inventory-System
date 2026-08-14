from django.test import TestCase

from customers.forms import CustomerForm
from customers.models import Customer


class CustomerFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "name": "  Acme Trading  ",
            "phone": "+60 12-345 6789",
            "email": "accounts@example.com",
            "address": "Kuala Lumpur",
        }
        data.update(overrides)
        return data

    def test_valid_form_trims_name_and_saves_customer(self):
        form = CustomerForm(data=self.valid_data())

        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()

        self.assertEqual(customer.name, "Acme Trading")
        self.assertTrue(customer.is_active)

    def test_name_is_required(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                form = CustomerForm(data=self.valid_data(name=name))
                self.assertFalse(form.is_valid())
                self.assertIn("name", form.errors)

    def test_phone_email_and_address_are_optional(self):
        form = CustomerForm(data=self.valid_data(phone="", email="", address=""))

        self.assertTrue(form.is_valid(), form.errors)

    def test_standard_email_validation_is_used(self):
        form = CustomerForm(data=self.valid_data(email="not-an-email"))

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_practical_phone_format_is_accepted(self):
        form = CustomerForm(data=self.valid_data(phone="03-1234 5678"))

        self.assertTrue(form.is_valid(), form.errors)

    def test_malformed_phone_is_rejected(self):
        form = CustomerForm(data=self.valid_data(phone="012-CALL-NOW"))

        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_duplicate_phone_and_email_are_allowed(self):
        Customer.objects.create(
            name="Existing Customer",
            phone="03-1234 5678",
            email="shared@example.com",
        )
        form = CustomerForm(
            data=self.valid_data(
                name="Another Customer",
                phone="03-1234 5678",
                email="shared@example.com",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_form_preserves_entered_name(self):
        form = CustomerForm(
            data=self.valid_data(name="Entered Customer", email="invalid")
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(form["name"].value(), "Entered Customer")

    def test_active_status_is_not_exposed(self):
        form = CustomerForm()

        self.assertNotIn("is_active", form.fields)
