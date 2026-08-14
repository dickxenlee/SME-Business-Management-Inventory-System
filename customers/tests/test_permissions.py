from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class CustomerPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="customer-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="customer-admin")
        cls.unassigned_user = user_model.objects.create_user(username="customer-none")
        cls.active_customer = Customer.objects.create(
            name="Active Customer",
            phone="012-345 6789",
        )
        cls.inactive_customer = Customer.objects.create(
            name="Inactive Customer",
            phone="03-1234 5678",
            is_active=False,
        )

    def test_anonymous_users_are_redirected_from_customer_pages(self):
        get_urls = (
            reverse("customers:list"),
            reverse("customers:create"),
            reverse("customers:detail", args=[self.active_customer.pk]),
            reverse("customers:edit", args=[self.active_customer.pk]),
        )

        for url in get_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("core:login"), response.url)

        response = self.client.post(
            reverse("customers:deactivate", args=[self.active_customer.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_admin_can_view_active_and_inactive_customers(self):
        self.client.force_login(self.admin_user)

        list_response = self.client.get(reverse("customers:list"))
        active_response = self.client.get(
            reverse("customers:detail", args=[self.active_customer.pk])
        )
        inactive_response = self.client.get(
            reverse("customers:detail", args=[self.inactive_customer.pk])
        )

        self.assertContains(list_response, self.active_customer.name)
        self.assertContains(list_response, self.inactive_customer.name)
        self.assertEqual(active_response.status_code, 200)
        self.assertEqual(inactive_response.status_code, 200)

    def test_admin_can_access_create_and_active_or_inactive_edit(self):
        self.client.force_login(self.admin_user)

        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("customers:edit", args=[self.active_customer.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse("customers:edit", args=[self.inactive_customer.pk])
            ).status_code,
            200,
        )

    def test_staff_can_view_active_customer_and_create_or_edit(self):
        self.client.force_login(self.staff_user)

        list_response = self.client.get(reverse("customers:list"))
        detail_response = self.client.get(
            reverse("customers:detail", args=[self.active_customer.pk])
        )

        self.assertContains(list_response, self.active_customer.name)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse("customers:edit", args=[self.active_customer.pk])
            ).status_code,
            200,
        )

    def test_staff_cannot_see_or_edit_inactive_customer(self):
        self.client.force_login(self.staff_user)

        list_response = self.client.get(reverse("customers:list"))
        detail_response = self.client.get(
            reverse("customers:detail", args=[self.inactive_customer.pk])
        )
        edit_response = self.client.get(
            reverse("customers:edit", args=[self.inactive_customer.pk])
        )

        self.assertNotContains(list_response, self.inactive_customer.name)
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(edit_response.status_code, 404)

    def test_staff_cannot_deactivate_customer(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("customers:deactivate", args=[self.active_customer.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Customer.objects.get(pk=self.active_customer.pk).is_active)

    def test_unassigned_authenticated_user_receives_forbidden(self):
        self.client.force_login(self.unassigned_user)

        for url in (reverse("customers:list"), reverse("customers:create")):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
