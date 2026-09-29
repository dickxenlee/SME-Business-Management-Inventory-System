"""Populate the staging demo with believable data and a shared login.

Kept out of the test fixtures deliberately: this exists so a visitor can open
the public demo and see a shop that has been trading, rather than a set of
empty tables with nothing to click.
"""

import os
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer
from inventory.models import StockMovement
from inventory.services import stock_in
from invoices.models import CreditNote, CreditNoteItem, Invoice, InvoiceItem
from invoices.services import issue_credit_note, issue_invoice
from products.models import Product
from sales.models import PaymentMethod, Sale, SaleItem, SaleReversal
from sales.services import create_sale, void_sale


DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo-shop-2026"

PRODUCTS = [
    ("COF-ARA-1K", "Arabica Coffee Beans 1kg", "48.00", "30.00", 60, 10),
    ("COF-ROB-1K", "Robusta Blend 1kg", "36.00", "22.00", 45, 10),
    ("TEA-BOH-500", "Boh Tea Carton 500g", "22.50", "14.00", 6, 10),
    ("EQP-GRIND-M", "Burr Grinder Manual", "185.00", "120.00", 4, 5),
    ("EQP-KETTLE", "Gooseneck Drip Kettle 1L", "120.00", "78.00", 9, 5),
    ("EQP-TAMPER", "Espresso Tamper 58mm", "45.00", "28.00", 14, 5),
    ("ACC-MUG-350", "Ceramic Mug 350ml", "15.00", "6.50", 0, 8),
    ("ACC-FILT-100", "Paper Filter Pack 100s", "12.00", "5.00", 140, 20),
    ("ACC-CANIST", "Airtight Storage Canister", "32.00", "18.00", 22, 8),
    ("ACC-BOTTLE", "Cold Brew Bottle 750ml", "55.00", "33.00", 17, 8),
]

CUSTOMERS = [
    ("Kedai Kopi Aman", "012-3456789", "aman@example.com",
     "12 Jalan Bunga Raya\n50100 Kuala Lumpur"),
    ("Warung Seri Muda", "019-8887766", "seri@example.com",
     "5 Lorong Damai\n46000 Petaling Jaya"),
    ("Cafe Lumiere", "03-22334455", "hello@example.com",
     "88 Jalan Sultan\n50000 Kuala Lumpur"),
    ("Hotel Serena Supplies", "03-77889900", "purchasing@example.com",
     "1 Persiaran Bukit\n47800 Petaling Jaya"),
    ("Pasar Mini Harmoni", "011-24681357", "harmoni@example.com",
     "3 Jalan Melur\n68000 Ampang"),
]


class Command(BaseCommand):
    help = "Create demonstration data and a shared demo login for the staging site."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Delete every Sale, Invoice, credit note, stock movement, "
                "Product and Customer first. Destroys real business records."
            ),
        )
        parser.add_argument(
            "--only-if-empty",
            action="store_true",
            help=(
                "Do nothing if the database already holds data. Safe to leave "
                "in a build command that runs on every deploy."
            ),
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help=(
                "Required when DJANGO_ENVIRONMENT is production. The public "
                "demo runs as production, so seeding it is deliberate."
            ),
        )

    def handle(self, *args, **options):
        if getattr(settings, "IS_PRODUCTION", False) and not options["allow_production"]:
            raise CommandError(
                "DJANGO_ENVIRONMENT is production. Re-run with "
                "--allow-production if this really is the demo site, never "
                "against a database holding real trading records."
            )

        existing = Sale.objects.exists() or Product.objects.exists()
        # Hosts without a shell can only seed from the build command, which
        # reruns on every deploy. This makes that safe: seed a fresh database,
        # leave an established one alone.
        if existing and options["only_if_empty"]:
            self.stdout.write("Database already has data; leaving it alone.")
            return
        if existing and not options["reset"]:
            raise CommandError(
                "This database already holds Products or Sales. Re-run with "
                "--reset to replace them, after checking they are not real."
            )

        with transaction.atomic():
            if options["reset"]:
                self._wipe()
            self._owner_if_requested()
            user = self._demo_user()
            products = self._products(user)
            customers = self._customers()
            self._trading_history(user, products, customers)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"  Sign in as: {DEMO_USERNAME} / {DEMO_PASSWORD}")
        self.stdout.write(
            f"  {Product.objects.count()} products, "
            f"{Customer.objects.count()} customers, "
            f"{Sale.objects.count()} sales, "
            f"{Invoice.objects.count()} invoices."
        )

    def _wipe(self):
        """Order matters: the money records protect the things they point at."""
        CreditNoteItem.objects.all().delete()
        CreditNote.objects.all().delete()
        InvoiceItem.objects.all().delete()
        Invoice.objects.all().delete()
        SaleReversal.objects.all().delete()
        SaleItem.objects.all().delete()
        Sale.objects.all().delete()
        StockMovement.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()
        self.stdout.write("  Cleared existing records.")

    def _owner_if_requested(self):
        """Create the first owner from the environment, for hosts with no shell.

        A platform whose free tier has no shell gives no other way to run
        createsuperuser, so the credentials have to arrive as configuration.
        This is a concession for a public demo: on a deployment holding real
        records, create the owner interactively and leave these unset.
        """
        username = os.environ.get("DEMO_OWNER_USERNAME", "").strip()
        password = os.environ.get("DEMO_OWNER_PASSWORD", "")
        if not username or not password:
            return

        user_model = get_user_model()
        owner, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": os.environ.get("DEMO_OWNER_EMAIL", "").strip()},
        )
        if not created:
            # Never silently reset a password that somebody may have changed.
            self.stdout.write(f"  Owner {username} already exists; left as is.")
            return
        owner.is_staff = True
        owner.is_superuser = True
        owner.is_active = True
        owner.set_password(password)
        owner.save()
        self.stdout.write(f"  Created owner {username}.")

    def _demo_user(self):
        """A Staff account, not an owner.

        Visitors can run the shop -- take sales, add stock, issue invoices --
        but voiding, crediting and deactivating stay owner-only, so a curious
        visitor cannot quietly destroy the data everyone else is looking at.
        """
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(
            username=DEMO_USERNAME,
            defaults={"email": "demo@example.com"},
        )
        user.is_staff = False
        user.is_superuser = False
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()
        group, _ = Group.objects.get_or_create(name="Staff")
        user.groups.add(group)
        return user

    def _products(self, user):
        created = []
        for sku, name, price, cost, stock, threshold in PRODUCTS:
            product = Product.objects.create(
                sku=sku,
                name=name,
                selling_price=Decimal(price),
                cost_price=Decimal(cost),
                low_stock_threshold=threshold,
            )
            if stock:
                stock_in(
                    product_id=product.pk,
                    quantity=stock,
                    performed_by=user,
                    reason="Opening stock",
                )
                # stock_in works on its own locked copy, so this instance is
                # still holding the pre-stock value of zero.
                product.refresh_from_db()
            created.append(product)
        return created

    def _customers(self):
        return [
            Customer.objects.create(
                name=name, phone=phone, email=email, address=address
            )
            for name, phone, email, address in CUSTOMERS
        ]

    def _trading_history(self, user, products, customers):
        """Sales spread across the reporting window.

        The dashboard and reports cover today, 7 days and 30 days, so the
        dates have to span that range or every period but one looks empty.
        """
        random.seed(20260927)
        invoiced = []

        for days_ago in [
            27, 25, 22, 20, 18, 16, 14, 13, 11, 10,
            8, 7, 6, 5, 4, 3, 3, 2, 2, 1, 1, 0, 0, 0,
        ]:
            # Re-read each round: every Sale depletes stock, and stale
            # in-memory counts would eventually oversell and abort the seed.
            pool = list(
                Product.objects.filter(is_active=True, current_stock__gt=3)
            )
            if not pool:
                break
            lines = random.sample(pool, min(random.randint(1, 3), len(pool)))
            items = []
            for product in lines:
                quantity = random.randint(1, min(3, product.current_stock))
                item = {"product_id": product.pk, "quantity": quantity}
                # Roughly one line in five carries a discount.
                if random.random() < 0.2:
                    item["discount_amount"] = (
                        product.selling_price * quantity * Decimal("0.1")
                    ).quantize(Decimal("0.01"))
                items.append(item)

            method = random.choice(
                [
                    PaymentMethod.CASH,
                    PaymentMethod.CASH,
                    PaymentMethod.CARD,
                    PaymentMethod.EWALLET,
                    PaymentMethod.TRANSFER,
                ]
            )
            customer = random.choice(customers) if random.random() < 0.6 else None

            sale = create_sale(
                customer_id=customer.pk if customer else None,
                items=items,
                created_by=user,
                payment_method=method,
            )
            if method == PaymentMethod.CASH:
                self._record_cash(sale)

            when = self._moment_days_ago(days_ago)
            self._backdate(sale, when)

            # Named customers usually want a document; walk-ins usually do not.
            if customer is not None and random.random() < 0.7:
                invoice = issue_invoice(sale_id=sale.pk, issued_by=user)
                Invoice.objects.filter(pk=invoice.pk).update(issued_at=when)
                invoiced.append(invoice)

        self._show_both_ways_of_undoing(user, invoiced)

    def _moment_days_ago(self, days_ago):
        """A time on the local calendar day that many days back.

        The reporting periods are built from local calendar dates, so the
        offset has to be applied to the local date rather than subtracted
        from a UTC instant. Doing the latter puts a "today" Sale into
        yesterday whenever the server clock is behind local midnight, which
        leaves the Today period empty on a machine running in UTC.
        """
        local_now = timezone.localtime()
        target = local_now.date() - timedelta(days=days_ago)
        if days_ago == 0:
            # Nothing in the future, and nothing before local midnight.
            hour = random.randint(0, local_now.hour)
            minute = (
                random.randint(0, local_now.minute)
                if hour == local_now.hour
                else random.randint(0, 59)
            )
        else:
            hour = random.randint(8, 20)
            minute = random.randint(0, 59)
        return timezone.make_aware(
            datetime.combine(target, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _record_cash(self, sale):
        """Round the tender up to a note, the way a customer actually pays."""
        tendered = (sale.total_amount / 50).to_integral_value(rounding="ROUND_CEILING") * 50
        Sale.objects.filter(pk=sale.pk).update(
            amount_tendered=tendered,
            change_given=tendered - sale.total_amount,
        )

    def _backdate(self, sale, when):
        Sale.objects.filter(pk=sale.pk).update(created_at=when)
        StockMovement.objects.filter(
            sale_item__sale_id=sale.pk
        ).update(created_at=when)

    def _show_both_ways_of_undoing(self, user, invoiced):
        """Leave one void and one credit note in the data.

        They are the least obvious features in the system, and a visitor who
        never clicks into them would not know either exists.
        """
        owner = self._owner_for_corrections(user)

        uninvoiced = (
            Sale.objects.not_cancelled()
            .filter(invoice__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if uninvoiced is not None:
            void_sale(
                sale_id=uninvoiced.pk,
                reason="Rang up twice by mistake",
                voided_by=owner,
            )

        if invoiced:
            issue_credit_note(
                invoice_id=invoiced[0].pk,
                reason="Customer returned the goods unopened",
                issued_by=owner,
            )

    def _owner_for_corrections(self, fallback):
        """Voiding and crediting are owner-only, so attribute them to an owner
        if one exists rather than to the demo account."""
        owner = (
            get_user_model()
            .objects.filter(is_superuser=True, is_active=True)
            .order_by("pk")
            .first()
        )
        return owner or fallback
