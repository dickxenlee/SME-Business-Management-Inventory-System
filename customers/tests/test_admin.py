from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class CustomerAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="customer-admin",
            password="test-password-123",
        )
        cls.customer = Customer.objects.create(name="Admin Customer")

    def test_customer_admin_disallows_physical_deletion(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:customers_customer_delete", args=[self.customer.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
