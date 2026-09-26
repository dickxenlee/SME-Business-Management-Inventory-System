"""Invoice issuance operations."""

from decimal import Decimal

from django.conf import settings
from django.db import transaction

from sales.models import Sale

from inventory.services import InventoryOperationError, stock_in

from .models import CreditNote, CreditNoteItem, Invoice, InvoiceItem


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

    # A voided Sale's goods went back and its money was returned. Invoicing it
    # would hand the customer a document for a Sale that no longer counts.
    if hasattr(sale, "reversal"):
        raise InvoiceOperationError(
            f"{sale.sale_number} was voided and cannot be invoiced"
        )

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
        item.unit_price * item.quantity - item.discount_amount != item.subtotal
        for item in sale_items
    ):
        raise InvoiceOperationError("Sale item arithmetic is invalid")

    # Line subtotals are net of discount and before tax, so they reconcile
    # against net_amount rather than the tax-inclusive total.
    calculated_net = sum(
        (item.subtotal for item in sale_items),
        start=Decimal("0.00"),
    )
    if calculated_net != sale.net_amount:
        raise InvoiceOperationError("Sale item subtotals do not match the Sale total")
    if sale.net_amount + sale.tax_amount != sale.total_amount:
        raise InvoiceOperationError("Sale tax does not reconcile with its total")

    invoice = Invoice.objects.create(
        sale=sale,
        customer_name=sale.customer_name,
        customer_address=sale.customer_address,
        seller_name=seller_name,
        seller_address=seller_address,
        net_amount=sale.net_amount,
        tax_rate=sale.tax_rate,
        tax_amount=sale.tax_amount,
        tax_label=sale.tax_label,
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
                discount_amount=item.discount_amount,
                subtotal=item.subtotal,
            )
            for item in sale_items
        ]
    )
    return invoice


class CreditNoteOperationError(Exception):
    """Raised when a credit note cannot be issued safely."""


@transaction.atomic
def issue_credit_note(*, invoice_id, reason, issued_by):
    """Cancel an issued Invoice with a credit note and return the stock.

    The Invoice and the Sale behind it are left exactly as they are. The
    customer already holds that Invoice, so the correction is its own numbered
    document rather than an edit to a document that is out in the world.
    """
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise CreditNoteOperationError(
            "A reason is required to issue a credit note"
        )

    try:
        invoice = (
            Invoice.objects.select_for_update()
            .select_related("sale")
            .prefetch_related("items")
            .get(pk=invoice_id)
        )
    except Invoice.DoesNotExist as exc:
        raise CreditNoteOperationError("Invoice is not available") from exc

    if hasattr(invoice, "credit_note"):
        raise CreditNoteOperationError(
            f"{invoice.invoice_number} has already been credited"
        )

    sale_items = list(invoice.sale.items.select_related("product"))
    if not sale_items:
        raise CreditNoteOperationError(
            "The Sale behind this Invoice has no items to return"
        )

    credit_note = CreditNote.objects.create(
        invoice=invoice,
        reason=normalized_reason,
        customer_name=invoice.customer_name,
        customer_address=invoice.customer_address,
        seller_name=invoice.seller_name,
        seller_address=invoice.seller_address,
        net_amount=invoice.net_amount,
        tax_rate=invoice.tax_rate,
        tax_amount=invoice.tax_amount,
        tax_label=invoice.tax_label,
        total_amount=invoice.total_amount,
        issued_by=issued_by,
    )
    CreditNoteItem.objects.bulk_create(
        [
            CreditNoteItem(
                credit_note=credit_note,
                product_sku=item.product_sku,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount_amount=item.discount_amount,
                subtotal=item.subtotal,
            )
            for item in invoice.items.all()
        ]
    )

    for item in sale_items:
        try:
            stock_in(
                product_id=item.product_id,
                quantity=item.quantity,
                performed_by=issued_by,
                reason=f"Credit note for {invoice.invoice_number}",
                # The Product may have been discontinued since it was sold;
                # the goods still come back.
                allow_inactive=True,
            )
        except InventoryOperationError as exc:
            raise CreditNoteOperationError(str(exc)) from exc

    return credit_note
