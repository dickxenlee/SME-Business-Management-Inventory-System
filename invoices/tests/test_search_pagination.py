from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from invoices.models import Invoice
from sales.models import Sale


class InvoiceSearchPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = get_user_model().objects.create_user(
            username="invoice-search-staff"
        )
        cls.staff_user.groups.add(staff_group)

        cls.invoices = []
        for number in range(1, 26):
            sale = Sale.objects.create(
                customer_name=f"Customer {number:03d}",
                customer_address="",
                net_amount=Decimal("10.00"),
                total_amount=Decimal("10.00"),
                created_by=cls.staff_user,
            )
            cls.invoices.append(
                Invoice.objects.create(
                    sale=sale,
                    customer_name=sale.customer_name,
                    customer_address="",
                    seller_name="Search SME",
                    seller_address="Search Address",
                    net_amount=sale.total_amount,
                    total_amount=sale.total_amount,
                    issued_by=cls.staff_user,
                )
            )

        special_sale = Sale.objects.create(
            customer_name="Kedai Maju",
            customer_address="",
            net_amount=Decimal("20.00"),
            total_amount=Decimal("20.00"),
            created_by=cls.staff_user,
        )
        cls.special = Invoice.objects.create(
            sale=special_sale,
            customer_name="Kedai Maju",
            customer_address="",
            seller_name="Search SME",
            seller_address="Search Address",
            net_amount=special_sale.total_amount,
            total_amount=special_sale.total_amount,
            issued_by=cls.staff_user,
        )
        cls.previous_day = timezone.localdate() - timedelta(days=1)
        Invoice.objects.filter(pk=cls.special.pk).update(
            issued_at=timezone.now() - timedelta(days=1)
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_search_by_customer_snapshot_is_case_insensitive(self):
        response = self.client.get(reverse("invoices:list"), {"q": "kedai maju"})

        self.assertEqual(list(response.context["invoices"]), [self.special])

    def test_search_by_derived_invoice_number(self):
        target = self.invoices[7]

        response = self.client.get(
            reverse("invoices:list"),
            {"q": target.invoice_number.lower()},
        )

        self.assertEqual(list(response.context["invoices"]), [target])

    def test_search_by_derived_sale_number(self):
        target = self.invoices[8]

        response = self.client.get(
            reverse("invoices:list"),
            {"q": target.sale.sale_number.lower()},
        )

        self.assertEqual(list(response.context["invoices"]), [target])

    def test_exact_date_filter_uses_local_issue_date(self):
        response = self.client.get(
            reverse("invoices:list"),
            {"date": self.previous_day.isoformat()},
        )

        self.assertEqual(list(response.context["invoices"]), [self.special])

    def test_pagination_uses_twenty_invoices_per_page(self):
        response = self.client.get(reverse("invoices:list"), {"q": "Customer"})

        self.assertEqual(len(response.context["invoices"]), 20)
        self.assertEqual(response.context["paginator"].per_page, 20)

    def test_second_page_contains_remaining_invoices(self):
        response = self.client.get(
            reverse("invoices:list"),
            {"q": "Customer", "page": 2},
        )

        self.assertEqual(len(response.context["invoices"]), 5)

    def test_search_and_date_are_preserved_in_pagination_links(self):
        today = timezone.localdate().isoformat()

        response = self.client.get(
            reverse("invoices:list"),
            {"q": "Customer", "date": today},
        )

        self.assertContains(
            response,
            f"?page=2&amp;q=Customer&amp;date={today}",
        )

    def test_no_results_render_empty_state(self):
        response = self.client.get(
            reverse("invoices:list"),
            {"q": "not-found"},
        )

        self.assertContains(response, "No invoices found")
