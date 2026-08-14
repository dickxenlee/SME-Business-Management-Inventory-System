from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse

from invoices.models import Invoice
from products.models import Product
from sales.models import Sale
from sales.services import create_sale


@override_settings(
    INVOICE_SELLER_NAME="Permission SME",
    INVOICE_SELLER_ADDRESS="Permission Business Address",
)
class InvoicePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="invoice-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(
            username="invoice-admin",
            password="test-password-123",
        )
        cls.unassigned_user = user_model.objects.create_user(
            username="invoice-unassigned"
        )
        cls.sale = Sale.objects.create(
            customer_name="Permission Customer",
            customer_address="Permission Address",
            total_amount=Decimal("10.00"),
            created_by=cls.admin_user,
        )
        cls.invoice = Invoice.objects.create(
            sale=cls.sale,
            customer_name=cls.sale.customer_name,
            customer_address=cls.sale.customer_address,
            seller_name="Permission SME",
            seller_address="Permission Address",
            total_amount=cls.sale.total_amount,
            issued_by=cls.admin_user,
        )
        cls.product = Product.objects.create(
            sku="INV-PERMISSION",
            name="Permission Product",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            current_stock=20,
        )
        cls.unissued_sale = create_sale(
            customer_id=None,
            items=[{"product_id": cls.product.pk, "quantity": 1}],
            created_by=cls.admin_user,
        )

    def test_anonymous_user_is_redirected_from_invoice_list(self):
        response = self.client.get("/invoices/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_staff_user_can_access_invoice_list(self):
        self.client.force_login(self.staff_user)
        self.client.raise_request_exception = False

        response = self.client.get("/invoices/")

        self.assertEqual(response.status_code, 200)

    def test_staff_user_can_access_invoice_detail(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(f"/invoices/{self.invoice.pk}/")

        self.assertEqual(response.status_code, 200)

    def test_admin_user_can_access_invoice_list_and_detail(self):
        self.client.force_login(self.admin_user)

        responses = (
            self.client.get(reverse("invoices:list")),
            self.client.get(reverse("invoices:detail", args=[self.invoice.pk])),
        )

        self.assertTrue(all(response.status_code == 200 for response in responses))

    def test_unassigned_user_receives_forbidden_for_list_and_detail(self):
        self.client.force_login(self.unassigned_user)

        responses = (
            self.client.get(reverse("invoices:list")),
            self.client.get(reverse("invoices:detail", args=[self.invoice.pk])),
        )

        self.assertTrue(all(response.status_code == 403 for response in responses))

    def test_anonymous_user_is_redirected_from_invoice_detail(self):
        response = self.client.get(
            reverse("invoices:detail", args=[self.invoice.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_staff_and_admin_can_issue_invoice(self):
        for user in (self.staff_user, self.admin_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.post(
                    reverse("invoices:issue", args=[self.unissued_sale.pk])
                )

                invoice = Invoice.objects.get(sale=self.unissued_sale)
                self.assertRedirects(
                    response,
                    reverse("invoices:detail", args=[invoice.pk]),
                )
                invoice.delete()

    def test_unassigned_user_cannot_issue_invoice(self):
        self.client.force_login(self.unassigned_user)

        response = self.client.post(
            reverse("invoices:issue", args=[self.unissued_sale.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Invoice.objects.filter(sale=self.unissued_sale).exists())

    def test_anonymous_user_is_redirected_from_issuance(self):
        response = self.client.post(
            reverse("invoices:issue", args=[self.unissued_sale.pk])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)
        self.assertFalse(Invoice.objects.filter(sale=self.unissued_sale).exists())
