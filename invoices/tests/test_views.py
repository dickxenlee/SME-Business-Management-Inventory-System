from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from invoices.models import Invoice
from invoices.services import issue_invoice
from products.models import Product
from sales.services import create_sale


@override_settings(
    INVOICE_SELLER_NAME="View SME",
    INVOICE_SELLER_ADDRESS="View Business Address",
)
class InvoiceViewTests(TestCase):
    def setUp(self):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        self.user = get_user_model().objects.create_user(username="invoice-view-staff")
        self.user.groups.add(staff_group)
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            sku="INV-VIEW",
            name="Invoice View Product",
            selling_price=Decimal("20.00"),
            cost_price=Decimal("10.00"),
            current_stock=5,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            created_by=self.user,
        )

    def test_post_issues_invoice_and_redirects_to_detail(self):
        response = self.client.post(f"/invoices/issue/{self.sale.pk}/")

        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get()
        self.assertRedirects(response, f"/invoices/{invoice.pk}/")
        self.assertEqual(invoice.sale, self.sale)
        self.assertEqual(invoice.issued_by, self.user)

    def test_sale_detail_switches_from_issue_action_to_invoice_link(self):
        sale_response = self.client.get(reverse("sales:detail", args=[self.sale.pk]))

        self.assertContains(sale_response, "Issue invoice")
        self.assertContains(sale_response, reverse("invoices:issue", args=[self.sale.pk]))

        invoice = Invoice.objects.create(
            sale=self.sale,
            customer_name=self.sale.customer_name,
            customer_address=self.sale.customer_address,
            seller_name="View SME",
            seller_address="View Business Address",
            net_amount=self.sale.total_amount,
            total_amount=self.sale.total_amount,
            issued_by=self.user,
        )
        invoice_response = self.client.get(
            reverse("sales:detail", args=[self.sale.pk])
        )

        self.assertContains(invoice_response, "View invoice")
        self.assertContains(
            invoice_response,
            reverse("invoices:detail", args=[invoice.pk]),
        )
        self.assertNotContains(invoice_response, "Issue invoice")

    def test_list_and_detail_render_invoice_snapshots_and_print_action(self):
        invoice = issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        list_response = self.client.get(reverse("invoices:list"))
        detail_response = self.client.get(
            reverse("invoices:detail", args=[invoice.pk])
        )

        self.assertTemplateUsed(list_response, "invoices/invoice_list.html")
        self.assertTemplateUsed(detail_response, "invoices/invoice_detail.html")
        self.assertContains(list_response, invoice.invoice_number)
        self.assertContains(list_response, self.sale.sale_number)
        self.assertContains(detail_response, "View SME")
        self.assertContains(detail_response, "View Business Address")
        self.assertContains(detail_response, "Walk-in Customer")
        self.assertContains(detail_response, "INV-VIEW")
        self.assertContains(detail_response, "Invoice View Product")
        self.assertContains(detail_response, "RM 40.00")
        self.assertContains(detail_response, "window.print()")
        self.assertContains(detail_response, 'class="invoice-document')

    def test_issue_endpoint_rejects_get(self):
        response = self.client.get(reverse("invoices:issue", args=[self.sale.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertFalse(Invoice.objects.exists())

    def test_issue_post_without_csrf_token_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(
            reverse("invoices:issue", args=[self.sale.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Invoice.objects.exists())

    def test_repeated_issue_post_redirects_to_the_existing_invoice(self):
        invoice = issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        response = self.client.post(reverse("invoices:issue", args=[self.sale.pk]))

        self.assertRedirects(
            response,
            reverse("invoices:detail", args=[invoice.pk]),
        )
        self.assertEqual(Invoice.objects.count(), 1)

    @override_settings(INVOICE_SELLER_NAME="", INVOICE_SELLER_ADDRESS="")
    def test_missing_seller_configuration_returns_clear_sale_detail_error(self):
        response = self.client.post(
            reverse("invoices:issue", args=[self.sale.pk]),
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse("sales:detail", args=[self.sale.pk]),
        )
        self.assertContains(
            response,
            "Invoice seller name and address must be configured before issuing",
        )
        self.assertFalse(Invoice.objects.exists())

    def test_invoice_edit_delete_and_reissue_routes_do_not_exist(self):
        invoice = issue_invoice(sale_id=self.sale.pk, issued_by=self.user)

        paths = (
            f"/invoices/{invoice.pk}/edit/",
            f"/invoices/{invoice.pk}/delete/",
            f"/invoices/{invoice.pk}/reissue/",
        )

        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_invoices_navigation_is_visible_to_staff(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("invoices:list"))
