from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class OpeningBalanceMigrationTests(TransactionTestCase):
    migrate_from = [("inventory", "0001_initial")]
    migrate_to = [("inventory", "0002_backfill_opening_stock")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        product_model = old_apps.get_model("products", "Product")
        self.stocked_product_id = product_model.objects.create(
            sku="OPENING-5",
            name="Opening Stock",
            selling_price=10,
            cost_price=5,
            current_stock=5,
        ).pk
        self.zero_product_id = product_model.objects.create(
            sku="OPENING-0",
            name="Zero Stock",
            selling_price=10,
            cost_price=5,
            current_stock=0,
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_nonzero_stock_gets_one_opening_movement_without_balance_change(self):
        product_model = self.apps.get_model("products", "Product")
        movement_model = self.apps.get_model("inventory", "StockMovement")

        product = product_model.objects.get(pk=self.stocked_product_id)
        movements = movement_model.objects.filter(product_id=product.pk)

        self.assertEqual(product.current_stock, 5)
        self.assertEqual(movements.count(), 1)
        movement = movements.get()
        self.assertEqual(movement.movement_type, "ADJUSTMENT")
        self.assertEqual(movement.quantity, 5)
        self.assertEqual(movement.previous_stock, 0)
        self.assertEqual(movement.new_stock, 5)
        self.assertIsNone(movement.performed_by_id)
        self.assertEqual(movement.reason, "Opening balance migrated from Phase 3")

    def test_zero_stock_gets_no_opening_movement(self):
        movement_model = self.apps.get_model("inventory", "StockMovement")

        self.assertFalse(
            movement_model.objects.filter(product_id=self.zero_product_id).exists()
        )
