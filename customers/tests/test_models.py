from django.core.exceptions import ValidationError
from django.test import TestCase

from customers.models import Customer


class CustomerModelTests(TestCase):
    def customer(self, **overrides):
        values = {
            "name": "Acme Trading",
            "phone": "+60 12-345 6789",
            "email": "accounts@example.com",
            "address": "Kuala Lumpur",
        }
        values.update(overrides)
        return Customer(**values)

    def test_valid_customer_saves_with_active_status_and_timestamps(self):
        customer = self.customer()

        customer.full_clean()
        customer.save()

        self.assertTrue(customer.is_active)
        self.assertIsNotNone(customer.created_at)
        self.assertIsNotNone(customer.updated_at)

    def test_name_is_trimmed(self):
        customer = self.customer(name="  Acme Trading  ")

        customer.full_clean()

        self.assertEqual(customer.name, "Acme Trading")

    def test_blank_and_whitespace_names_are_rejected(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                customer = self.customer(name=name)
                with self.assertRaises(ValidationError) as context:
                    customer.full_clean()
                self.assertIn("name", context.exception.message_dict)

    def test_phone_and_email_are_optional(self):
        customer = self.customer(phone="", email="")

        customer.full_clean()
        customer.save()

        self.assertEqual(customer.phone, "")
        self.assertEqual(customer.email, "")

    def test_practical_phone_formats_are_valid(self):
        valid_numbers = (
            "012-345 6789",
            "03-1234 5678",
            "+60 12-345 6789",
            "(03) 1234-5678",
        )

        for phone in valid_numbers:
            with self.subTest(phone=phone):
                self.customer(phone=phone).full_clean()

    def test_malformed_phone_values_are_rejected(self):
        invalid_numbers = (
            "123",
            "012-CALL-NOW",
            "+60/12/3456789",
            "++60123456789",
        )

        for phone in invalid_numbers:
            with self.subTest(phone=phone):
                with self.assertRaises(ValidationError) as context:
                    self.customer(phone=phone).full_clean()
                self.assertIn("phone", context.exception.message_dict)

    def test_duplicate_phone_and_email_are_allowed(self):
        first = self.customer()
        first.full_clean()
        first.save()
        second = self.customer(name="Another Customer")

        second.full_clean()
        second.save()

        self.assertEqual(Customer.objects.count(), 2)

    def test_deactivation_preserves_customer_row(self):
        customer = self.customer()
        customer.save()

        customer.is_active = False
        customer.save(update_fields=["is_active", "updated_at"])

        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())
        self.assertFalse(Customer.objects.get(pk=customer.pk).is_active)
