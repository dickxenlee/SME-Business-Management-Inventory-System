import os
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.demo import DEMO_PASSWORD
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
            "/accounts/login/", {"username": "demo", "password": DEMO_PASSWORD}
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
        self.assertIn(DEMO_PASSWORD, output)


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


class SeedDemoOnlyIfEmptyTests(TestCase):
    """Hosts with no shell can only seed from a build command that reruns."""

    def test_it_seeds_an_empty_database(self):
        seed(only_if_empty=True)

        self.assertEqual(Product.objects.count(), 10)

    def test_it_leaves_an_established_database_alone(self):
        seed()
        sale_count = Sale.objects.count()
        Customer.objects.create(name="Added by a real user")

        output = seed(only_if_empty=True)

        self.assertIn("leaving it alone", output)
        self.assertEqual(Sale.objects.count(), sale_count)
        self.assertTrue(
            Customer.objects.filter(name="Added by a real user").exists()
        )

    def test_it_still_refuses_production_without_the_flag(self):
        with override_settings(IS_PRODUCTION=True):
            with self.assertRaisesMessage(CommandError, "production"):
                seed(only_if_empty=True)


class SeedDemoOwnerTests(TestCase):
    """createsuperuser needs a shell, which a free instance does not have."""

    def test_no_owner_is_created_without_the_environment_variables(self):
        seed()

        self.assertFalse(
            get_user_model().objects.filter(is_superuser=True).exists()
        )

    def test_an_owner_is_created_from_the_environment(self):
        with patch.dict(
            os.environ,
            {
                "DEMO_OWNER_USERNAME": "shopowner",
                "DEMO_OWNER_PASSWORD": "owner-pass-8812",
                "DEMO_OWNER_EMAIL": "owner@example.com",
            },
        ):
            seed()

        owner = get_user_model().objects.get(username="shopowner")
        self.assertTrue(owner.is_superuser)
        self.assertTrue(owner.is_staff)
        self.assertEqual(owner.email, "owner@example.com")

    def test_an_existing_owner_password_is_never_overwritten(self):
        """A redeploy must not silently reset a password somebody changed."""
        existing = get_user_model().objects.create_superuser(
            username="shopowner", password="the-password-i-chose"
        )

        with patch.dict(
            os.environ,
            {
                "DEMO_OWNER_USERNAME": "shopowner",
                "DEMO_OWNER_PASSWORD": "whatever-is-in-the-config",
            },
        ):
            output = seed()

        existing.refresh_from_db()
        self.assertTrue(existing.check_password("the-password-i-chose"))
        self.assertIn("already exists", output)

    def test_a_username_without_a_password_creates_nothing(self):
        with patch.dict(os.environ, {"DEMO_OWNER_USERNAME": "shopowner"}):
            seed()

        self.assertFalse(
            get_user_model().objects.filter(username="shopowner").exists()
        )


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class SeedDemoAcrossTheDateLineTests(TestCase):
    """The reporting periods use local calendar dates, not UTC instants.

    CI runs in UTC. When UTC is still on the previous day but Kuala Lumpur has
    already rolled over, subtracting hours from a UTC "now" pushes a Sale
    meant for today into yesterday, and the Today period renders empty.
    """

    def test_today_has_sales_just_after_local_midnight(self):
        from reports.services import get_sales_report, resolve_period

        # 16:20 UTC is 00:20 the next day in Kuala Lumpur: the window where
        # the old arithmetic lost every one of today's Sales.
        just_past_local_midnight = timezone.now().replace(
            hour=16, minute=20, second=0, microsecond=0
        )
        with patch(
            "django.utils.timezone.now", return_value=just_past_local_midnight
        ):
            seed()
            report = get_sales_report(resolve_period("today"))

        self.assertGreater(report["sale_count"], 0)

    def test_no_sale_is_dated_in_the_future(self):
        seed()

        self.assertFalse(Sale.objects.filter(created_at__gt=timezone.now()).exists())
