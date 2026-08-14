from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from inventory.models import StockMovement
from products.models import Product
from reports.services import get_inventory_report, resolve_period

from .test_utils import local_datetime


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class InventoryReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff = get_user_model().objects.create_user(username="report-staff")
        cls.staff.groups.add(staff_group)
        cls.admin = get_user_model().objects.create_superuser(username="report-admin")
        cls.healthy = Product.objects.create(
            sku="HEALTHY", name="Healthy", selling_price=10, cost_price=5,
            current_stock=10, low_stock_threshold=5,
        )
        cls.low = Product.objects.create(
            sku="LOW", name="Low", selling_price=10, cost_price=5,
            current_stock=3, low_stock_threshold=5,
        )
        cls.out = Product.objects.create(
            sku="OUT", name="Out", selling_price=10, cost_price=5,
            current_stock=0, low_stock_threshold=5,
        )
        cls.inactive = Product.objects.create(
            sku="INACTIVE", name="Inactive", selling_price=10, cost_price=5,
            current_stock=1, low_stock_threshold=5, is_active=False,
        )

    def create_movement(self, product, movement_type, quantity, previous, new, reason):
        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            previous_stock=previous,
            new_stock=new,
            reason=reason,
            performed_by=self.admin,
        )
        StockMovement.objects.filter(pk=movement.pk).update(
            created_at=local_datetime(2026, 8, 14)
        )
        return movement

    def test_current_health_counts_only_active_products(self):
        report = get_inventory_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date()),
            self.admin,
        )

        self.assertEqual(report["active_products"], 3)
        self.assertEqual(report["low_stock"], 1)
        self.assertEqual(report["out_of_stock"], 1)

    def test_movement_metrics_keep_adjustment_activity_and_net_distinct(self):
        self.create_movement(self.healthy, "STOCK_IN", 5, 5, 10, "Delivery")
        self.create_movement(self.healthy, "STOCK_OUT", 2, 10, 8, "Damage")
        self.create_movement(self.low, "ADJUSTMENT", 4, 7, 3, "Count down")
        self.create_movement(self.out, "ADJUSTMENT", 2, 0, 2, "Count up")

        report = get_inventory_report(
            resolve_period("today", today=local_datetime(2026, 8, 14).date()),
            self.admin,
        )

        self.assertEqual(report["stock_in_units"], 5)
        self.assertEqual(report["stock_out_units"], 2)
        self.assertEqual(report["adjustment_count"], 2)
        self.assertEqual(report["adjustment_activity"], 6)
        self.assertEqual(report["net_adjustment"], -2)

    def test_staff_excludes_inactive_product_movements_but_admin_includes_them(self):
        self.create_movement(self.inactive, "STOCK_IN", 3, 0, 3, "Inactive history")
        period = resolve_period("today", today=local_datetime(2026, 8, 14).date())

        staff_report = get_inventory_report(period, self.staff)
        admin_report = get_inventory_report(period, self.admin)

        self.assertEqual(staff_report["stock_in_units"], 0)
        self.assertEqual(admin_report["stock_in_units"], 3)
        self.assertEqual(staff_report["recent_movements"], [])
        self.assertEqual(len(admin_report["recent_movements"]), 1)
