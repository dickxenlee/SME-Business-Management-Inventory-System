from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from products.models import Product


class StockMovementHistoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.staff_user = user_model.objects.create_user(username="history-staff")
        cls.staff_user.groups.add(staff_group)
        cls.admin_user = user_model.objects.create_superuser(username="history-admin")
        cls.keyboard = Product.objects.create(
            sku="HIS-KEY",
            name="History Keyboard",
            selling_price=20,
            cost_price=10,
        )
        cls.mouse = Product.objects.create(
            sku="HIS-MSE",
            name="History Mouse",
            selling_price=20,
            cost_price=10,
        )
        cls.inactive = Product.objects.create(
            sku="HIS-OFF",
            name="Inactive History Product",
            selling_price=20,
            cost_price=10,
            is_active=False,
        )
        cls.keyboard_in = cls.create_movement(
            cls.keyboard,
            StockMovement.MovementType.STOCK_IN,
            "Keyboard delivery",
        )
        cls.mouse_out = cls.create_movement(
            cls.mouse,
            StockMovement.MovementType.STOCK_OUT,
            "Mouse damage",
        )
        cls.create_movement(
            cls.inactive,
            StockMovement.MovementType.ADJUSTMENT,
            "Inactive count",
        )

        for number in range(22):
            cls.create_movement(
                cls.keyboard,
                StockMovement.MovementType.STOCK_IN,
                f"Page movement {number:02d}",
            )

    @classmethod
    def create_movement(cls, product, movement_type, reason):
        return StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=1,
            previous_stock=1,
            new_stock=2 if movement_type == StockMovement.MovementType.STOCK_IN else 0,
            reason=reason,
            performed_by=cls.admin_user,
        )

    def test_history_renders_useful_movement_fields(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("inventory:history"), {"q": "HIS-MSE"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HIS-MSE")
        self.assertContains(response, "History Mouse")
        self.assertContains(response, "Stock Out")
        self.assertContains(response, "Mouse damage")
        self.assertContains(response, self.admin_user.username)

    def test_search_matches_sku_and_product_name(self):
        self.client.force_login(self.staff_user)

        sku_response = self.client.get(reverse("inventory:history"), {"q": "HIS-MSE"})
        name_response = self.client.get(
            reverse("inventory:history"),
            {"q": "history mouse"},
        )

        self.assertContains(sku_response, "Mouse damage")
        self.assertContains(name_response, "HIS-MSE")
        self.assertNotContains(sku_response, "Keyboard delivery")

    def test_filter_by_movement_type(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("inventory:history"),
            {"movement_type": StockMovement.MovementType.STOCK_OUT},
        )

        self.assertContains(response, "Mouse damage")
        self.assertNotContains(response, "Keyboard delivery")

    def test_search_and_type_filter_can_be_combined(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("inventory:history"),
            {"q": "History Mouse", "movement_type": "STOCK_OUT"},
        )

        self.assertEqual(len(response.context["stock_movements"]), 1)
        self.assertEqual(response.context["stock_movements"][0], self.mouse_out)

    def test_history_uses_twenty_movements_per_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("inventory:history"), {"q": "HIS-KEY"})

        self.assertEqual(len(response.context["stock_movements"]), 20)
        self.assertEqual(response.context["paginator"].per_page, 20)

    def test_filters_are_preserved_in_pagination_links(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("inventory:history"),
            {"q": "HIS-KEY", "movement_type": "STOCK_IN"},
        )

        self.assertContains(
            response,
            "?page=2&amp;q=HIS-KEY&amp;movement_type=STOCK_IN",
        )

    def test_staff_history_excludes_inactive_products(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("inventory:history"))

        self.assertNotContains(response, "Inactive count")

    def test_admin_history_includes_inactive_products(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("inventory:history"), {"q": "HIS-OFF"})

        self.assertContains(response, "Inactive count")
