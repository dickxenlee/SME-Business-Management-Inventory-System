from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from inventory.services import MAX_STOCK_QUANTITY
from products.models import Product


class InventoryViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="inventory-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="inventory-admin")
        cls.product = Product.objects.create(
            sku="VIEW-1",
            name="View Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
        )
        cls.inactive_product = Product.objects.create(
            sku="VIEW-OFF",
            name="Inactive View Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
            is_active=False,
        )

    def test_stock_in_form_lists_only_active_products(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("inventory:stock_in"))

        queryset = response.context["form"].fields["product"].queryset
        self.assertIn(self.product, queryset)
        self.assertNotIn(self.inactive_product, queryset)

    def test_product_can_be_preselected_from_query_parameter(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("inventory:stock_out"),
            {"product": self.product.pk},
        )

        self.assertEqual(
            response.context["form"].initial["product"],
            str(self.product.pk),
        )

    def test_staff_stock_in_updates_stock_and_redirects_to_history(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("inventory:stock_in"),
            {
                "product": self.product.pk,
                "quantity": 3,
                "reason": "Supplier delivery",
            },
        )

        self.product.refresh_from_db()
        self.assertRedirects(response, reverse("inventory:history"))
        self.assertEqual(self.product.current_stock, 8)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_staff_stock_out_updates_stock_and_redirects_to_history(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("inventory:stock_out"),
            {"product": self.product.pk, "quantity": 2, "reason": "Damaged"},
        )

        self.product.refresh_from_db()
        self.assertRedirects(response, reverse("inventory:history"))
        self.assertEqual(self.product.current_stock, 3)
        self.assertEqual(StockMovement.objects.get().new_stock, 3)

    def test_excessive_stock_out_renders_error_without_writes(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("inventory:stock_out"),
            {"product": self.product.pk, "quantity": 6, "reason": "Damaged"},
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient stock")
        self.assertEqual(self.product.current_stock, 5)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_inactive_product_post_is_rejected_without_writes(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("inventory:stock_in"),
            {"product": self.inactive_product.pk, "quantity": 1, "reason": "Test"},
        )

        self.inactive_product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(self.inactive_product.current_stock, 5)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_admin_adjustment_records_final_stock(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("inventory:adjustment"),
            {
                "product": self.product.pk,
                "new_stock": 2,
                "reason": "Physical count correction",
            },
        )

        self.product.refresh_from_db()
        movement = StockMovement.objects.get()
        self.assertRedirects(response, reverse("inventory:history"))
        self.assertEqual(self.product.current_stock, 2)
        self.assertEqual(movement.previous_stock, 5)
        self.assertEqual(movement.new_stock, 2)
        self.assertEqual(movement.quantity, 3)

    def test_adjustment_form_requires_reason(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("inventory:adjustment"),
            {"product": self.product.pk, "new_stock": 2, "reason": ""},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "reason", "This field is required.")
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_stock_in_form_rejects_quantity_above_database_maximum(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("inventory:stock_in"),
            {
                "product": self.product.pk,
                "quantity": MAX_STOCK_QUANTITY + 1,
                "reason": "Too large",
            },
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "quantity",
            f"Ensure this value is less than or equal to {MAX_STOCK_QUANTITY}.",
        )
        self.assertEqual(self.product.current_stock, 5)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_adjustment_form_rejects_target_above_database_maximum(self):
        self.client.force_login(self.admin_user)

        response = self.client.post(
            reverse("inventory:adjustment"),
            {
                "product": self.product.pk,
                "new_stock": MAX_STOCK_QUANTITY + 1,
                "reason": "Too large",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "new_stock",
            f"Ensure this value is less than or equal to {MAX_STOCK_QUANTITY}.",
        )
        self.assertEqual(StockMovement.objects.count(), 0)
