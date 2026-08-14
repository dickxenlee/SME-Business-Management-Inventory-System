from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from products.models import Product
from sales.models import SaleItem
from sales.services import create_sale


class SaleAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="sales-admin-user",
            password="test-password-123",
        )
        cls.product = Product.objects.create(
            sku="ADMIN-SALE-1",
            name="Admin Sale Product",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            current_stock=5,
        )
        cls.sale = create_sale(
            customer_id=None,
            items=[{"product_id": cls.product.pk, "quantity": 1}],
            created_by=cls.admin_user,
        )
        cls.item = cls.sale.items.get()

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_sale_admin_displays_read_only_sale_and_item(self):
        response = self.client.get(
            reverse("admin:sales_sale_change", args=[self.sale.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.sale.sale_number)
        self.assertContains(response, self.item.product_sku)

    def test_sale_admin_rejects_add_change_and_delete(self):
        responses = (
            self.client.get(reverse("admin:sales_sale_add")),
            self.client.post(
                reverse("admin:sales_sale_change", args=[self.sale.pk]),
                {"total_amount": "999.00", "_save": "Save"},
            ),
            self.client.get(
                reverse("admin:sales_sale_delete", args=[self.sale.pk])
            ),
        )

        self.assertTrue(all(response.status_code == 403 for response in responses))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.total_amount, Decimal("10.00"))

    def test_sale_item_admin_rejects_add_change_and_delete(self):
        responses = (
            self.client.get(reverse("admin:sales_saleitem_add")),
            self.client.post(
                reverse("admin:sales_saleitem_change", args=[self.item.pk]),
                {"quantity": "99", "_save": "Save"},
            ),
            self.client.get(
                reverse("admin:sales_saleitem_delete", args=[self.item.pk])
            ),
        )

        self.assertTrue(all(response.status_code == 403 for response in responses))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 1)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_sale_deletion_is_not_available_as_bulk_action(self):
        response = self.client.get(reverse("admin:sales_sale_changelist"))

        self.assertNotContains(response, 'value="delete_selected"')
        self.assertTrue(SaleItem.objects.filter(pk=self.item.pk).exists())
