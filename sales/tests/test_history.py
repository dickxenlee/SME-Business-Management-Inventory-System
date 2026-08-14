from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Customer
from products.models import Product
from sales.services import create_sale


class SaleHistoricalSnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="sale-history-user")

    def test_later_metadata_changes_and_deactivation_do_not_change_snapshots(self):
        customer = Customer.objects.create(
            name="Historical Customer",
            address="Historical Address",
        )
        product = Product.objects.create(
            sku="HISTORY-1",
            name="Historical Product",
            selling_price=Decimal("19.90"),
            cost_price=Decimal("10.00"),
            current_stock=5,
        )
        sale = create_sale(
            customer_id=customer.pk,
            items=[{"product_id": product.pk, "quantity": 2}],
            created_by=self.user,
        )

        customer.name = "Changed Customer"
        customer.address = "Changed Address"
        customer.is_active = False
        customer.save(update_fields=["name", "address", "is_active", "updated_at"])
        product.sku = "CHANGED-SKU"
        product.name = "Changed Product"
        product.selling_price = Decimal("99.00")
        product.is_active = False
        product.save(
            update_fields=["sku", "name", "selling_price", "is_active", "updated_at"]
        )

        sale.refresh_from_db()
        item = sale.items.get()
        self.assertEqual(sale.customer_name, "Historical Customer")
        self.assertEqual(sale.customer_address, "Historical Address")
        self.assertEqual(item.product_sku, "HISTORY-1")
        self.assertEqual(item.product_name, "Historical Product")
        self.assertEqual(item.unit_price, Decimal("19.90"))
        self.assertEqual(item.subtotal, Decimal("39.80"))
        self.assertEqual(sale.total_amount, Decimal("39.80"))
