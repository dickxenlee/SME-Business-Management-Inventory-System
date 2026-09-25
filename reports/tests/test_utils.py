from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from inventory.models import StockMovement
from invoices.models import Invoice
from sales.models import Sale, SaleItem


def local_datetime(year, month, day, hour=12, minute=0):
    return timezone.make_aware(
        datetime(year, month, day, hour, minute),
        timezone.get_current_timezone(),
    )


def days_ago(days, hour=12, minute=0):
    """A local datetime relative to today.

    Reporting periods roll forward every day, so fixtures must be anchored to
    the current date. A hard-coded calendar date silently falls outside the
    window once enough time passes and takes the assertions with it.
    """
    day = timezone.localdate() - timedelta(days=days)
    return local_datetime(day.year, day.month, day.day, hour, minute)


def create_sale(*, user, at, customer=None, items=(), record_cost=True, tax_rate=0):
    total = sum(
        (Decimal(str(unit_price)) * quantity for _, quantity, unit_price in items),
        start=Decimal("0.00"),
    )
    tax = (Decimal(str(tax_rate)) * total / Decimal("100")).quantize(Decimal("0.01"))
    sale = Sale.objects.create(
        customer=customer,
        customer_name=customer.name if customer else "",
        customer_address=customer.address if customer else "",
        net_amount=total,
        tax_rate=Decimal(str(tax_rate)),
        tax_amount=tax,
        total_amount=total + tax,
        created_by=user,
    )
    Sale.objects.filter(pk=sale.pk).update(created_at=at)
    sale.created_at = at

    for product, quantity, unit_price in items:
        unit_price = Decimal(str(unit_price))
        movement = StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.MovementType.STOCK_OUT,
            quantity=quantity,
            previous_stock=product.current_stock + quantity,
            new_stock=product.current_stock,
            reason=f"Sale {sale.sale_number}",
            performed_by=user,
        )
        StockMovement.objects.filter(pk=movement.pk).update(created_at=at)
        SaleItem.objects.create(
            sale=sale,
            product=product,
            stock_movement=movement,
            product_sku=product.sku,
            product_name=product.name,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=unit_price * quantity,
            unit_cost=product.cost_price if record_cost else None,
            cost_subtotal=(
                product.cost_price * quantity if record_cost else None
            ),
        )
    return sale


def create_invoice(*, sale, user, at):
    invoice = Invoice.objects.create(
        sale=sale,
        customer_name=sale.customer_name,
        customer_address=sale.customer_address,
        seller_name="Reporting SME",
        seller_address="Kuala Lumpur",
        net_amount=sale.net_amount,
        tax_rate=sale.tax_rate,
        tax_amount=sale.tax_amount,
        total_amount=sale.total_amount,
        issued_by=user,
    )
    Invoice.objects.filter(pk=invoice.pk).update(issued_at=at)
    invoice.issued_at = at
    return invoice
