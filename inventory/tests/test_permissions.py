from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from inventory.models import StockMovement
from products.models import Product


class InventoryPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="permission-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="permission-admin")
        cls.unassigned_user = user_model.objects.create_user(username="permission-none")
        cls.product = Product.objects.create(
            sku="PERMISSION-1",
            name="Permission Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
        )

    def test_anonymous_users_are_redirected_from_inventory_pages(self):
        urls = (
            reverse("inventory:history"),
            reverse("inventory:stock_in"),
            reverse("inventory:stock_out"),
            reverse("inventory:adjustment"),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("core:login"), response.url)

    def test_admin_can_access_every_inventory_page(self):
        self.client.force_login(self.admin_user)

        for url in (
            reverse("inventory:history"),
            reverse("inventory:stock_in"),
            reverse("inventory:stock_out"),
            reverse("inventory:adjustment"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_access_history_stock_in_and_stock_out(self):
        self.client.force_login(self.staff_user)

        for url in (
            reverse("inventory:history"),
            reverse("inventory:stock_in"),
            reverse("inventory:stock_out"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_cannot_access_or_post_adjustment(self):
        self.client.force_login(self.staff_user)
        url = reverse("inventory:adjustment")

        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url,
                {"product": self.product.pk, "new_stock": 3, "reason": "Count"},
            ).status_code,
            403,
        )
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_unassigned_user_receives_forbidden(self):
        self.client.force_login(self.unassigned_user)

        for url in (
            reverse("inventory:history"),
            reverse("inventory:stock_in"),
            reverse("inventory:stock_out"),
            reverse("inventory:adjustment"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_stock_operation_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff_user)

        response = csrf_client.post(
            reverse("inventory:stock_in"),
            {"product": self.product.pk, "quantity": 1},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(StockMovement.objects.count(), 0)
