"""Invoice issuance operations."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from sales.models import Sale

from .models import Invoice, InvoiceItem


class InvoiceOperationError(Exception):
    """Raised when an Invoice cannot be issued safely."""


@transaction.atomic
def issue_invoice(*, sale_id, issued_by):
    try:
        sale = (
            Sale.objects.select_for_update()
            .prefetch_related("items")
            .get(pk=sale_id)
        )
    except Sale.DoesNotExist as exc:
        raise InvoiceOperationError("Sale is not available") from exc
    existing_invoice = Invoice.objects.filter(sale=sale).first()
    if existing_invoice is not None:
        return existing_invoice

    seller_name = getattr(settings, "INVOICE_SELLER_NAME", "").strip()
    seller_address = getattr(settings, "INVOICE_SELLER_ADDRESS", "").strip()
    if not seller_name or not seller_address:
        raise InvoiceOperationError(
            "Invoice seller name and address must be configured before issuing"
        )
    sale_items = list(sale.items.all())
    if not sale_items:
        raise InvoiceOperationError("Sale has no items and cannot be invoiced")

    if any(
        item.unit_price * item.quantity != item.subtotal
        for item in sale_items
    ):
        raise InvoiceOperationError("Sale item arithmetic is invalid")

    calculated_total = sum(
        (item.subtotal for item in sale_items),
        start=Decimal("0.00"),
    )
    if calculated_total != sale.total_amount:
        raise InvoiceOperationError("Sale item subtotals do not match the Sale total")

    invoice = Invoice.objects.create(
        sale=sale,
        customer_name=sale.customer_name,
        customer_address=sale.customer_address,
        seller_name=seller_name,
        seller_address=seller_address,
        total_amount=sale.total_amount,
        issued_by=issued_by,
    )
    InvoiceItem.objects.bulk_create(
        [
            InvoiceItem(
                invoice=invoice,
                product_sku=item.product_sku,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                subtotal=item.subtotal,
            )
            for item in sale_items
        ]
    )
    return invoice
