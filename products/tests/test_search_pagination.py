from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class ProductSearchPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="admin")

        for number in range(1, 26):
            Product.objects.create(
                sku=f"KEY-{number:03d}",
                name=f"Keyboard {number:03d}",
                selling_price=number,
                cost_price=number,
                current_stock=number,
            )
        cls.mouse = Product.objects.create(
            sku="MSE-001",
            name="Wireless Mouse",
            selling_price=50,
            cost_price=30,
        )
        cls.inactive_keyboard = Product.objects.create(
            sku="KEY-INACTIVE",
            name="Keyboard Inactive",
            selling_price=50,
            cost_price=30,
            is_active=False,
        )

    def test_search_by_sku(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "MSE-001"})

        self.assertContains(response, "Wireless Mouse")
        self.assertNotContains(response, "Keyboard 001")

    def test_search_by_product_name_is_case_insensitive(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "wireless mouse"})

        self.assertContains(response, "MSE-001")

    def test_no_result_search_renders_empty_state(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "not-found"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No products found")

    def test_pagination_uses_twenty_products_per_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "Keyboard"})

        self.assertEqual(len(response.context["products"]), 20)
        self.assertEqual(response.context["paginator"].per_page, 20)

    def test_second_page_contains_remaining_products(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("products:list"),
            {"q": "Keyboard", "page": 2},
        )

        self.assertEqual(len(response.context["products"]), 5)

    def test_search_query_is_preserved_in_pagination_links(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "Keyboard"})

        self.assertContains(response, "?page=2&amp;q=Keyboard")

    def test_staff_search_does_not_expose_inactive_products(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("products:list"), {"q": "Inactive"})

        self.assertNotContains(response, self.inactive_keyboard.sku)

    def test_admin_search_includes_inactive_products(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("products:list"), {"q": "Inactive"})

        self.assertContains(response, self.inactive_keyboard.sku)

    def test_products_navigation_is_visible_to_staff(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("products:list"))
