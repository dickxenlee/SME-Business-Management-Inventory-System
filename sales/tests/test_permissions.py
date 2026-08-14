from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from sales.models import Sale


class SalePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="sales-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="sales-admin")
        cls.unassigned_user = user_model.objects.create_user(username="sales-none")
        cls.sale = Sale.objects.create(
            customer=None,
            customer_name="",
            customer_address="",
            total_amount=Decimal("10.00"),
            created_by=cls.admin_user,
        )

    def sale_urls(self):
        return (
            reverse("sales:list"),
            reverse("sales:create"),
            reverse("sales:detail", args=[self.sale.pk]),
        )

    def test_anonymous_users_are_redirected_to_login(self):
        for url in self.sale_urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("core:login"), response.url)

    def test_admin_can_list_create_and_view_sales(self):
        self.client.force_login(self.admin_user)

        for url in self.sale_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_list_create_and_view_sales(self):
        self.client.force_login(self.staff_user)

        for url in self.sale_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_unassigned_user_receives_forbidden(self):
        self.client.force_login(self.unassigned_user)

        for url in self.sale_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_no_edit_cancel_or_delete_routes_exist(self):
        for name in ("edit", "cancel", "delete"):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(f"sales:{name}", args=[self.sale.pk])
