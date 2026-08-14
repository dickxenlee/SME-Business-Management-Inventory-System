from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from sales.models import Sale


class SaleSearchPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="sales-search-staff")
        cls.staff_user.groups.add(staff_group)

        cls.sales = []
        for number in range(1, 26):
            cls.sales.append(
                Sale.objects.create(
                    customer=None,
                    customer_name=f"Customer {number:03d}",
                    customer_address="",
                    total_amount=Decimal("10.00"),
                    created_by=cls.staff_user,
                )
            )
        cls.special = Sale.objects.create(
            customer=None,
            customer_name="Kedai Maju",
            customer_address="",
            total_amount=Decimal("20.00"),
            created_by=cls.staff_user,
        )
        cls.previous_day = timezone.localdate() - timedelta(days=1)
        Sale.objects.filter(pk=cls.special.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )

    def setUp(self):
        self.client.force_login(self.staff_user)

    def test_search_by_customer_snapshot_is_case_insensitive(self):
        response = self.client.get(reverse("sales:list"), {"q": "kedai maju"})

        self.assertContains(response, self.special.sale_number)
        self.assertNotContains(response, self.sales[0].sale_number)

    def test_search_by_derived_sale_number(self):
        response = self.client.get(
            reverse("sales:list"),
            {"q": self.sales[7].sale_number.lower()},
        )

        self.assertContains(response, self.sales[7].sale_number)
        self.assertNotContains(response, self.sales[0].sale_number)

    def test_exact_date_filter_uses_local_sale_date(self):
        response = self.client.get(
            reverse("sales:list"),
            {"date": self.previous_day.isoformat()},
        )

        self.assertContains(response, self.special.sale_number)
        self.assertNotContains(response, self.sales[0].sale_number)

    def test_pagination_uses_twenty_sales_per_page(self):
        response = self.client.get(reverse("sales:list"), {"q": "Customer"})

        self.assertEqual(len(response.context["sales"]), 20)
        self.assertEqual(response.context["paginator"].per_page, 20)

    def test_second_page_contains_remaining_sales(self):
        response = self.client.get(
            reverse("sales:list"),
            {"q": "Customer", "page": 2},
        )

        self.assertEqual(len(response.context["sales"]), 5)

    def test_search_and_date_are_preserved_in_pagination_links(self):
        today = timezone.localdate().isoformat()
        response = self.client.get(
            reverse("sales:list"),
            {"q": "Customer", "date": today},
        )

        self.assertContains(
            response,
            f"?page=2&amp;q=Customer&amp;date={today}",
        )

    def test_no_results_render_empty_state(self):
        response = self.client.get(reverse("sales:list"), {"q": "not-found"})

        self.assertContains(response, "No sales found")

    def test_sales_navigation_is_visible_to_staff(self):
        response = self.client.get(reverse("core:home"))

        self.assertContains(response, reverse("sales:list"))
