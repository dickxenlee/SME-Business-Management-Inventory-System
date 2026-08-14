from datetime import datetime
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


def create_sale(*, user, at, customer=None, items=()):
    total = sum(
        (Decimal(str(unit_price)) * quantity for _, quantity, unit_price in items),
        start=Decimal("0.00"),
    )
    sale = Sale.objects.create(
        customer=customer,
        customer_name=customer.name if customer else "",
        customer_address=customer.address if customer else "",
        total_amount=total,
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
        )
    return sale


def create_invoice(*, sale, user, at):
    invoice = Invoice.objects.create(
        sale=sale,
        customer_name=sale.customer_name,
        customer_address=sale.customer_address,
        seller_name="Reporting SME",
        seller_address="Kuala Lumpur",
        total_amount=sale.total_amount,
        issued_by=user,
    )
    Invoice.objects.filter(pk=invoice.pk).update(issued_at=at)
    invoice.issued_at = at
    return invoice
