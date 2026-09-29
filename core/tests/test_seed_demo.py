from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from customers.models import Customer
from invoices.models import CreditNote, Invoice
from products.models import Product
from sales.models import Sale, SaleReversal
from sales.services import create_sale


def seed(**options):
    out = StringIO()
    call_command("seed_demo", stdout=out, **options)
    return out.getvalue()


class SeedDemoGuardTests(TestCase):
    """The command deletes business records, so it must be hard to misfire."""

    def test_it_refuses_to_run_over_existing_data(self):
        Product.objects.create(
            sku="REAL-1",
            name="A real product",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("4.00"),
        )

        with self.assertRaisesMessage(CommandError, "already holds Products or Sales"):
            seed()

        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().sku, "REAL-1")

    @override_settings(IS_PRODUCTION=True)
    def test_it_refuses_to_run_in_production_without_an_explicit_flag(self):
        with self.assertRaisesMessage(CommandError, "DJANGO_ENVIRONMENT is production"):
            seed()

        self.assertFalse(Product.objects.exists())

    @override_settings(IS_PRODUCTION=True)
    def test_the_production_flag_lets_the_demo_site_be_seeded(self):
        seed(allow_production=True)

        self.assertTrue(Product.objects.exists())

    def test_the_production_guard_is_checked_before_anything_is_deleted(self):
        """Otherwise --reset would wipe real data and then refuse to continue."""
        Product.objects.create(
            sku="REAL-2",
            name="A real product",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("4.00"),
        )

        with override_settings(IS_PRODUCTION=True):
            with self.assertRaises(CommandError):
                seed(reset=True)

        self.assertEqual(Product.objects.count(), 1)


class SeedDemoContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()

    def test_it_creates_a_shop_that_looks_like_it_has_been_trading(self):
        self.assertEqual(Product.objects.count(), 10)
        self.assertEqual(Customer.objects.count(), 5)
        self.assertGreaterEqual(Sale.objects.count(), 15)
        self.assertGreaterEqual(Invoice.objects.count(), 1)

    def test_the_demo_account_can_run_the_shop_but_not_own_it(self):
        demo = get_user_model().objects.get(username="demo")

        self.assertTrue(demo.is_active)
        self.assertTrue(demo.groups.filter(name="Staff").exists())
        # is_staff gates Django admin; is_superuser gates voiding, crediting
        # and account management. A curious visitor must reach none of them.
        self.assertFalse(demo.is_staff)
        self.assertFalse(demo.is_superuser)

    def test_the_demo_account_can_actually_sign_in(self):
        self.client.post(
            "/accounts/login/", {"username": "demo", "password": "demo-shop-2026"}
        )

        self.assertIn("_auth_user_id", self.client.session)

    def test_every_reporting_period_has_something_in_it(self):
        """A visitor switching to Today must not land on an empty dashboard."""
        from reports.services import get_sales_report, resolve_period

        for period in ["today", "7d", "30d"]:
            with self.subTest(period=period):
                report = get_sales_report(resolve_period(period))
                self.assertGreater(report["sale_count"], 0)
                self.assertGreater(report["revenue"], Decimal("0.00"))

    def test_the_stock_warnings_have_something_to_show(self):
        self.assertTrue(Product.objects.filter(current_stock=0).exists())
        self.assertTrue(
            Product.objects.filter(
                current_stock__gt=0, current_stock__lte=10
            ).exists()
        )

    def test_both_ways_of_undoing_a_sale_are_represented(self):
        """Voids and credit notes are the least discoverable features, so the
        demo leaves one of each to click into."""
        self.assertEqual(SaleReversal.objects.count(), 1)
        self.assertEqual(CreditNote.objects.count(), 1)

    def test_undone_sales_are_excluded_from_the_headline_figures(self):
        counted = Sale.objects.not_cancelled().count()

        self.assertEqual(counted, Sale.objects.count() - 2)

    def test_cash_sales_record_the_change_given(self):
        cash_sales = Sale.objects.filter(payment_method="CASH")

        self.assertTrue(cash_sales.exists())
        for sale in cash_sales:
            with self.subTest(sale=sale.sale_number):
                self.assertIsNotNone(sale.change_given)
                self.assertEqual(
                    sale.change_given, sale.amount_tendered - sale.total_amount
                )

    def test_it_reports_the_credentials_it_created(self):
        # --reset rather than a manual delete: Sales are protected by their
        # reversals, so clearing them is the command's job to sequence.
        output = seed(reset=True)

        self.assertIn("demo", output)
        self.assertIn("demo-shop-2026", output)


class SeedDemoResetTests(TestCase):
    def test_reset_replaces_everything_including_linked_records(self):
        seed()
        first_run_skus = set(Product.objects.values_list("sku", flat=True))
        self.assertTrue(Invoice.objects.exists())

        seed(reset=True)

        self.assertEqual(
            set(Product.objects.values_list("sku", flat=True)), first_run_skus
        )
        self.assertEqual(Product.objects.count(), 10)
        # Nothing orphaned from the previous run.
        self.assertFalse(
            Invoice.objects.exclude(sale__in=Sale.objects.all()).exists()
        )

    def test_reset_clears_records_that_protect_each_other(self):
        """Sales protect Products, Invoices protect Sales: a naive delete
        would fail on the foreign keys."""
        seed()
        product = Product.objects.filter(current_stock__gt=2).first()
        create_sale(
            customer_id=None,
            items=[{"product_id": product.pk, "quantity": 1}],
            created_by=get_user_model().objects.get(username="demo"),
        )

        seed(reset=True)

        self.assertEqual(Product.objects.count(), 10)
