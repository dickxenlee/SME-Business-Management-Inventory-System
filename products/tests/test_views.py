from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from products.models import Product


class ProductViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="product-admin",
            password="test-password-123",
        )
        cls.product = Product.objects.create(
            sku="PRD-001",
            name="Mechanical Keyboard",
            selling_price="199.90",
            cost_price="120.00",
            current_stock=3,
            low_stock_threshold=3,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def product_data(self, **overrides):
        data = {
            "sku": "prd-new",
            "name": "New Product",
            "selling_price": "49.90",
            "cost_price": "30.00",
            "current_stock": "7",
            "low_stock_threshold": "2",
        }
        data.update(overrides)
        return data

    def test_product_list_renders(self):
        response = self.client.get(reverse("products:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/product_list.html")
        self.assertContains(response, self.product.name)

    def test_product_detail_renders_stock_status(self):
        response = self.client.get(reverse("products:detail", args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/product_detail.html")
        self.assertContains(response, "Low stock")

    def test_zero_stock_renders_out_of_stock_status(self):
        self.product.current_stock = 0
        self.product.save(update_fields=["current_stock", "updated_at"])

        response = self.client.get(reverse("products:detail", args=[self.product.pk]))

        self.assertContains(response, "Out of stock")

    def test_valid_product_creation_works(self):
        response = self.client.post(reverse("products:create"), self.product_data())

        product = Product.objects.get(sku="PRD-NEW")
        self.assertRedirects(response, reverse("products:detail", args=[product.pk]))

    def test_invalid_product_creation_fails_without_saving(self):
        response = self.client.post(
            reverse("products:create"),
            self.product_data(sku="INVALID", selling_price="-1"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/product_form.html")
        self.assertFalse(Product.objects.filter(sku="INVALID").exists())
        self.assertContains(response, "Ensure this value is greater than or equal to")

    def test_product_editing_works(self):
        response = self.client.post(
            reverse("products:edit", args=[self.product.pk]),
            self.product_data(
                sku="prd-001",
                name="Updated Keyboard",
                current_stock="9",
            ),
        )

        self.product.refresh_from_db()
        self.assertRedirects(
            response,
            reverse("products:detail", args=[self.product.pk]),
        )
        self.assertEqual(self.product.name, "Updated Keyboard")
        self.assertEqual(self.product.current_stock, 9)

    def test_invalid_edit_leaves_stored_product_unchanged(self):
        response = self.client.post(
            reverse("products:edit", args=[self.product.pk]),
            self.product_data(sku="prd-001", name="Unsafe update", current_stock="-1"),
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.name, "Mechanical Keyboard")
        self.assertEqual(self.product.current_stock, 3)

    def test_post_deactivation_preserves_row_and_sets_inactive(self):
        response = self.client.post(
            reverse("products:deactivate", args=[self.product.pk])
        )

        self.assertRedirects(response, reverse("products:list"))
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(Product.objects.get(pk=self.product.pk).is_active)

    def test_get_cannot_deactivate_product(self):
        response = self.client.get(
            reverse("products:deactivate", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Product.objects.get(pk=self.product.pk).is_active)

    def test_deactivation_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        response = csrf_client.post(
            reverse("products:deactivate", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.get(pk=self.product.pk).is_active)

    def test_deactivating_inactive_product_is_idempotent(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active", "updated_at"])

        response = self.client.post(
            reverse("products:deactivate", args=[self.product.pk])
        )

        self.assertRedirects(response, reverse("products:list"))
        self.assertFalse(Product.objects.get(pk=self.product.pk).is_active)
