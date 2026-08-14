from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from inventory.services import stock_in
from products.admin import ProductAdmin
from products.forms import ProductForm
from products.models import Product


class InventoryProductIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="integration-admin",
            password="test-password-123",
        )
        cls.product = Product.objects.create(
            sku="INTEGRATION-1",
            name="Integration Product",
            selling_price=20,
            cost_price=10,
            current_stock=5,
            low_stock_threshold=2,
        )
        cls.movement = StockMovement.objects.create(
            product=cls.product,
            movement_type=StockMovement.MovementType.STOCK_IN,
            quantity=5,
            previous_stock=0,
            new_stock=5,
            reason="Opening stock",
            performed_by=cls.admin_user,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_product_admin_post_cannot_modify_current_stock(self):
        response = self.client.post(
            reverse("admin:products_product_change", args=[self.product.pk]),
            {
                "sku": self.product.sku,
                "name": "Updated in admin",
                "selling_price": "20.00",
                "cost_price": "10.00",
                "current_stock": "99",
                "low_stock_threshold": "2",
                "is_active": "on",
                "_save": "Save",
            },
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.product.name, "Updated in admin")
        self.assertEqual(self.product.current_stock, 5)

    def test_stock_movement_admin_disallows_add_change_and_delete_posts(self):
        add_response = self.client.get(reverse("admin:inventory_stockmovement_add"))
        change_response = self.client.post(
            reverse(
                "admin:inventory_stockmovement_change",
                args=[self.movement.pk],
            ),
            {"quantity": 99, "_save": "Save"},
        )
        delete_response = self.client.get(
            reverse(
                "admin:inventory_stockmovement_delete",
                args=[self.movement.pk],
            )
        )

        self.assertEqual(add_response.status_code, 403)
        self.assertEqual(change_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.movement.refresh_from_db()
        self.assertEqual(self.movement.quantity, 5)

    def test_stock_movement_admin_allows_read_only_detail_view(self):
        response = self.client.get(
            reverse(
                "admin:inventory_stockmovement_change",
                args=[self.movement.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.sku)

    def test_product_detail_links_to_allowed_inventory_operations(self):
        response = self.client.get(reverse("products:detail", args=[self.product.pk]))

        self.assertContains(
            response,
            f'{reverse("inventory:stock_in")}?product={self.product.pk}',
        )
        self.assertContains(
            response,
            f'{reverse("inventory:stock_out")}?product={self.product.pk}',
        )
        self.assertContains(
            response,
            f'{reverse("inventory:adjustment")}?product={self.product.pk}',
        )

    def test_stale_product_form_save_does_not_overwrite_new_stock(self):
        stale_product = Product.objects.get(pk=self.product.pk)
        form = ProductForm(
            instance=stale_product,
            data={
                "sku": stale_product.sku,
                "name": "Metadata after stock",
                "selling_price": "20.00",
                "cost_price": "10.00",
                "low_stock_threshold": "2",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        stock_in(
            product_id=self.product.pk,
            quantity=2,
            performed_by=self.admin_user,
        )

        form.save()

        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Metadata after stock")
        self.assertEqual(self.product.current_stock, 7)

    def test_stale_product_admin_save_does_not_overwrite_new_stock(self):
        stale_product = Product.objects.get(pk=self.product.pk)
        stock_in(
            product_id=self.product.pk,
            quantity=2,
            performed_by=self.admin_user,
        )
        stale_product.name = "Admin metadata after stock"
        product_admin = ProductAdmin(Product, admin.site)
        request = type("Request", (), {"user": self.admin_user})()

        product_admin.save_model(request, stale_product, form=None, change=True)

        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Admin metadata after stock")
        self.assertEqual(self.product.current_stock, 7)
