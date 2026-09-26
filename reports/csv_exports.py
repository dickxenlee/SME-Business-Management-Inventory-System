"""Streaming CSV exports for reporting data."""

import csv

from django.db.models import Count, Q, Sum
from django.http import StreamingHttpResponse
from django.utils import timezone

from inventory.models import StockMovement
from sales.models import Sale


FORMULA_PREFIXES = ("=", "+", "-", "@")


class CsvBuffer:
    def write(self, value):
        return value


def safe_text(value):
    """Prevent spreadsheet software from executing user-controlled text."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def _local_timestamp(value):
    return timezone.localtime(value).isoformat(timespec="seconds")


def _stream_csv(*, rows, header, filename):
    writer = csv.writer(CsvBuffer())

    def serialized_rows():
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    response = StreamingHttpResponse(serialized_rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def sales_csv_response(period):
    queryset = (
        Sale.objects.filter(
            created_at__gte=period.start_at,
            created_at__lt=period.end_at,
            # Voided Sales went back; exporting them would overstate takings.
            reversal__isnull=True,
        )
        .select_related("created_by", "invoice")
        .annotate(
            item_count=Count("items", distinct=True),
            # Blank rather than zero when any line predates cost capture, so a
            # partial cost snapshot is never read as a full-margin Sale.
            cost_total=Sum("items__cost_subtotal"),
            uncosted_items=Count(
                "items", filter=Q(items__unit_cost__isnull=True), distinct=True
            ),
        )
        .order_by("-created_at", "-pk")
    )

    def rows():
        for sale in queryset.iterator(chunk_size=500):
            invoice = getattr(sale, "invoice", None)
            known_cost = sale.cost_total if not sale.uncosted_items else None
            yield (
                sale.sale_number,
                _local_timestamp(sale.created_at),
                safe_text(sale.customer_name or "Walk-in Customer"),
                sale.item_count,
                f"{sale.net_amount:.2f}",
                f"{sale.tax_amount:.2f}",
                f"{sale.total_amount:.2f}",
                f"{known_cost:.2f}" if known_cost is not None else "",
                # Profit comes off the net figure: tax is collected for the
                # government, so counting it as profit overstates earnings.
                f"{sale.net_amount - known_cost:.2f}"
                if known_cost is not None
                else "",
                invoice.invoice_number if invoice else "",
                sale.get_payment_method_display() if sale.payment_method else "",
                safe_text(sale.created_by.username if sale.created_by else ""),
            )

    return _stream_csv(
        rows=rows(),
        header=(
            "Sale number", "Date/time", "Customer", "Item count",
            "Net (MYR)", "Tax (MYR)", "Total (MYR)",
            "Cost (MYR)", "Gross profit (MYR)", "Invoice number",
            "Payment method", "Created by",
        ),
        filename=f"sales-{period.end_date.isoformat()}.csv",
    )


def inventory_movements_csv_response(period, user):
    queryset = StockMovement.objects.filter(
        created_at__gte=period.start_at,
        created_at__lt=period.end_at,
    ).select_related("product", "performed_by")
    if not user.is_superuser:
        queryset = queryset.filter(product__is_active=True)
    queryset = queryset.order_by("-created_at", "-pk")

    def rows():
        for movement in queryset.iterator(chunk_size=500):
            yield (
                _local_timestamp(movement.created_at),
                safe_text(movement.product.sku),
                safe_text(movement.product.name),
                movement.get_movement_type_display(),
                movement.quantity,
                movement.previous_stock,
                movement.new_stock,
                safe_text(movement.reason),
                safe_text(
                    movement.performed_by.username if movement.performed_by else ""
                ),
            )

    return _stream_csv(
        rows=rows(),
        header=(
            "Date/time", "SKU", "Product", "Movement type", "Quantity",
            "Previous stock", "New stock", "Reason", "Performed by",
        ),
        filename=f"inventory-movements-{period.end_date.isoformat()}.csv",
    )
