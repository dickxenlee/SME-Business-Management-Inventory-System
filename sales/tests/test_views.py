from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Customer
from inventory.models import StockMovement
from products.models import Product
from sales.models import Sale
from sales.services import create_sale


class SaleViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="sales-view-admin",
            password="test-password-123",
        )
        cls.customer = Customer.objects.create(
            name="View Customer",
            address="View Address",
        )

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.product = Product.objects.create(
            sku="VIEW-SALE-1",
            name="View Sale Product",
            selling_price=Decimal("15.00"),
            cost_price=Decimal("8.00"),
            current_stock=5,
        )

    def post_data(self, **overrides):
        data = {
            "customer": self.customer.pk,
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product.pk,
            "items-0-quantity": "2",
        }
        data.update(overrides)
        return data

    def test_list_create_and_detail_use_sales_templates(self):
        sale = create_sale(
            customer_id=self.customer.pk,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            created_by=self.admin_user,
        )

        list_response = self.client.get(reverse("sales:list"))
        create_response = self.client.get(reverse("sales:create"))
        detail_response = self.client.get(reverse("sales:detail", args=[sale.pk]))

        self.assertTemplateUsed(list_response, "sales/sale_list.html")
        self.assertTemplateUsed(create_response, "sales/sale_form.html")
        self.assertTemplateUsed(detail_response, "sales/sale_detail.html")
        self.assertContains(list_response, sale.sale_number)
        self.assertContains(detail_response, "VIEW-SALE-1")
        self.assertContains(detail_response, "RM 15.00")

    def test_valid_post_creates_sale_and_redirects_to_detail(self):
        response = self.client.post(reverse("sales:create"), self.post_data())

        sale = Sale.objects.get()
        self.assertRedirects(response, reverse("sales:detail", args=[sale.pk]))
        self.assertEqual(sale.total_amount, Decimal("30.00"))
        self.assertEqual(sale.created_by, self.admin_user)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_walk_in_post_creates_sale_without_customer(self):
        response = self.client.post(
            reverse("sales:create"),
            self.post_data(customer=""),
        )

        sale = Sale.objects.get()
        self.assertRedirects(response, reverse("sales:detail", args=[sale.pk]))
        self.assertIsNone(sale.customer)

    def test_invalid_formset_does_not_create_sale(self):
        response = self.client.post(
            reverse("sales:create"),
            self.post_data(**{"items-0-quantity": "0"}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ensure this value is greater than or equal to 1")
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_insufficient_stock_returns_error_without_partial_sale(self):
        response = self.client.post(
            reverse("sales:create"),
            self.post_data(**{"items-0-quantity": "6"}),
        )

        self.product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient stock")
        self.assertEqual(self.product.current_stock, 5)
        self.assertEqual(Sale.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_create_post_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        response = csrf_client.post(reverse("sales:create"), self.post_data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Sale.objects.count(), 0)

    def test_inactive_related_records_do_not_break_historical_detail(self):
        sale = create_sale(
            customer_id=self.customer.pk,
            items=[{"product_id": self.product.pk, "quantity": 1}],
            created_by=self.admin_user,
        )
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active", "updated_at"])
        self.product.is_active = False
        self.product.save(update_fields=["is_active", "updated_at"])

        response = self.client.get(reverse("sales:detail", args=[sale.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View Customer")
        self.assertContains(response, "VIEW-SALE-1")
