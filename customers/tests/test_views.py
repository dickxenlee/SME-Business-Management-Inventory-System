from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Customer


class CustomerViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="customer-view-admin",
            password="test-password-123",
        )
        cls.customer = Customer.objects.create(
            name="View Customer",
            phone="012-345 6789",
            email="view@example.com",
            address="Kuala Lumpur",
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def customer_data(self, **overrides):
        data = {
            "name": "New Customer",
            "phone": "+60 12-987 6543",
            "email": "new@example.com",
            "address": "Petaling Jaya",
        }
        data.update(overrides)
        return data

    def test_list_and_detail_render(self):
        list_response = self.client.get(reverse("customers:list"))
        detail_response = self.client.get(
            reverse("customers:detail", args=[self.customer.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertTemplateUsed(list_response, "customers/customer_list.html")
        self.assertContains(list_response, self.customer.name)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTemplateUsed(detail_response, "customers/customer_detail.html")
        self.assertContains(detail_response, self.customer.email)

    def test_valid_customer_creation_works(self):
        response = self.client.post(reverse("customers:create"), self.customer_data())

        customer = Customer.objects.get(name="New Customer")
        self.assertRedirects(response, reverse("customers:detail", args=[customer.pk]))

    def test_invalid_customer_creation_does_not_save(self):
        response = self.client.post(
            reverse("customers:create"),
            self.customer_data(name="", email="invalid"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customers/customer_form.html")
        self.assertFalse(Customer.objects.filter(email="invalid").exists())

    def test_customer_editing_works(self):
        response = self.client.post(
            reverse("customers:edit", args=[self.customer.pk]),
            self.customer_data(name="Updated Customer"),
        )

        self.customer.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("customers:detail", args=[self.customer.pk]),
        )
        self.assertEqual(self.customer.name, "Updated Customer")

    def test_post_deactivation_preserves_row_and_sets_inactive(self):
        response = self.client.post(
            reverse("customers:deactivate", args=[self.customer.pk])
        )

        self.assertRedirects(response, reverse("customers:list"))
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertFalse(Customer.objects.get(pk=self.customer.pk).is_active)

    def test_get_cannot_deactivate_customer(self):
        response = self.client.get(
            reverse("customers:deactivate", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Customer.objects.get(pk=self.customer.pk).is_active)

    def test_deactivation_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        response = csrf_client.post(
            reverse("customers:deactivate", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Customer.objects.get(pk=self.customer.pk).is_active)

    def test_repeated_deactivation_is_safe(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active", "updated_at"])

        response = self.client.post(
            reverse("customers:deactivate", args=[self.customer.pk])
        )

        self.assertRedirects(response, reverse("customers:list"))
        self.assertFalse(Customer.objects.get(pk=self.customer.pk).is_active)
