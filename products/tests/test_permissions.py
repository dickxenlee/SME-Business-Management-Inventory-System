from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from products.models import Product


class ProductPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(
            username="product-staff",
            password="test-password-123",
        )
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(
            username="product-admin",
            password="test-password-123",
        )
        cls.unassigned_user = user_model.objects.create_user(
            username="unassigned",
            password="test-password-123",
        )
        cls.active_product = Product.objects.create(
            sku="ACTIVE-1",
            name="Active Product",
            selling_price=20,
            cost_price=10,
        )
        cls.inactive_product = Product.objects.create(
            sku="INACTIVE-1",
            name="Inactive Product",
            selling_price=20,
            cost_price=10,
            is_active=False,
        )

    def test_anonymous_users_are_redirected_from_product_pages(self):
        urls = (
            reverse("products:list"),
            reverse("products:detail", args=[self.active_product.pk]),
            reverse("products:create"),
            reverse("products:edit", args=[self.active_product.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("core:login"), response.url)

        response = self.client.post(
            reverse("products:deactivate", args=[self.active_product.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_admin_can_view_active_and_inactive_products(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("products:list"))

        self.assertContains(response, self.active_product.name)
        self.assertContains(response, self.inactive_product.name)

    def test_staff_can_view_active_product_list_and_detail(self):
        self.client.force_login(self.staff_user)

        list_response = self.client.get(reverse("products:list"))
        detail_response = self.client.get(
            reverse("products:detail", args=[self.active_product.pk])
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.active_product.name)
        self.assertEqual(detail_response.status_code, 200)

    def test_staff_cannot_see_inactive_products(self):
        self.client.force_login(self.staff_user)

        list_response = self.client.get(reverse("products:list"))
        detail_response = self.client.get(
            reverse("products:detail", args=[self.inactive_product.pk])
        )

        self.assertNotContains(list_response, self.inactive_product.name)
        self.assertEqual(detail_response.status_code, 404)

    def test_staff_cannot_create_edit_or_deactivate_products(self):
        self.client.force_login(self.staff_user)

        self.assertEqual(self.client.get(reverse("products:create")).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("products:edit", args=[self.active_product.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("products:deactivate", args=[self.active_product.pk])
            ).status_code,
            403,
        )

    def test_authenticated_user_without_role_receives_forbidden(self):
        self.client.force_login(self.unassigned_user)

        response = self.client.get(reverse("products:list"))

        self.assertEqual(response.status_code, 403)

    def test_django_admin_does_not_allow_physical_product_deletion(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(
            reverse("admin:products_product_delete", args=[self.active_product.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.active_product.pk).exists())
