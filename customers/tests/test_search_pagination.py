from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer


class CustomerSearchPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="search-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="search-admin")

        for number in range(1, 26):
            Customer.objects.create(
                name=f"Customer {number:03d}",
                phone=f"012-555-{number:04d}",
                email=f"customer{number:03d}@example.com",
            )
        cls.special = Customer.objects.create(
            name="Kedai Maju",
            phone="03-7788 9900",
            email="owner@kedaimaju.my",
        )
        cls.inactive = Customer.objects.create(
            name="Inactive Customer",
            phone="011-000 0000",
            email="inactive@example.com",
            is_active=False,
        )

    def test_search_by_name_is_case_insensitive(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "kedai maju"})

        self.assertContains(response, "Kedai Maju")
        self.assertNotContains(response, "Customer 001")

    def test_search_by_phone(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "7788 9900"})

        self.assertContains(response, "Kedai Maju")

    def test_search_by_email_is_case_insensitive(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("customers:list"),
            {"q": "OWNER@KEDAIMAJU.MY"},
        )

        self.assertContains(response, "Kedai Maju")

    def test_no_result_search_renders_empty_state(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "not-found"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No customers found")

    def test_pagination_uses_twenty_customers_per_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "Customer"})

        self.assertEqual(len(response.context["customers"]), 20)
        self.assertEqual(response.context["paginator"].per_page, 20)

    def test_second_page_contains_remaining_customers(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("customers:list"),
            {"q": "Customer", "page": 2},
        )

        self.assertEqual(len(response.context["customers"]), 5)

    def test_search_query_is_preserved_in_pagination_links(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "Customer"})

        self.assertContains(response, "?page=2&amp;q=Customer")

    def test_staff_search_does_not_expose_inactive_customer(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("customers:list"), {"q": "Inactive"})

        self.assertNotContains(response, self.inactive.email)

    def test_admin_search_includes_inactive_customer(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("customers:list"), {"q": "Inactive"})

        self.assertContains(response, self.inactive.email)

    def test_customers_navigation_is_visible_to_staff(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("customers:list"))
