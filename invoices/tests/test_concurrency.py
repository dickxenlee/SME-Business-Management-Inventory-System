from decimal import Decimal
from threading import Barrier, Lock, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from invoices.models import Invoice, InvoiceItem
from invoices.services import issue_invoice
from inventory.models import StockMovement
from products.models import Product
from sales.services import create_sale


@override_settings(
    INVOICE_SELLER_NAME="Concurrent SME",
    INVOICE_SELLER_ADDRESS="Concurrent Business Address",
)
class InvoiceConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="invoice-concurrent")
        self.product = Product.objects.create(
            sku="INV-CONCURRENT",
            name="Concurrent Product",
            selling_price=Decimal("10.00"),
            cost_price=Decimal("5.00"),
            current_stock=5,
        )
        self.sale = create_sale(
            customer_id=None,
            items=[{"product_id": self.product.pk, "quantity": 2}],
            created_by=self.user,
        )

    def test_concurrent_issuance_creates_exactly_one_invoice(self):
        barrier = Barrier(3)
        result_lock = Lock()
        invoice_ids = []
        errors = []

        def issue():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                invoice = issue_invoice(
                    sale_id=self.sale.pk,
                    issued_by=self.user,
                )
                with result_lock:
                    invoice_ids.append(invoice.pk)
            except Exception as exc:  # pragma: no cover - asserted below
                with result_lock:
                    errors.append(exc)
            finally:
                close_old_connections()

        threads = [Thread(target=issue) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertFalse(errors)
        self.assertEqual(len(invoice_ids), 2)
        self.assertEqual(len(set(invoice_ids)), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(InvoiceItem.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.current_stock, 3)
        self.assertEqual(StockMovement.objects.count(), 1)
