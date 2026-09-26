from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction

from customers.models import Customer
from inventory.services import InventoryOperationError, stock_in, stock_out
from products.models import Product

from .models import PaymentMethod, Sale, SaleItem, SaleReversal


MAX_SALE_TOTAL = Decimal("9999999999999999999999.99")


class SalesOperationError(Exception):
    """Raised when a Sale cannot be completed without violating a rule."""


def _resolve_payment(payment_method, amount_tendered, total_amount):
    """Validate the payment and work out the change.

    Tendered and change are only meaningful for cash. Card and e-wallet take
    the exact amount, so recording a tendered figure there would invent a cash
    drawer movement that never happened.
    """
    if payment_method and payment_method not in PaymentMethod.values:
        raise SalesOperationError("Unknown payment method")

    if payment_method != PaymentMethod.CASH:
        return None, None
    if amount_tendered is None:
        return None, None

    try:
        tendered = Decimal(amount_tendered).quantize(Decimal("0.01"))
    except (ArithmeticError, TypeError, ValueError) as exc:
        raise SalesOperationError("Amount tendered must be an amount") from exc
    if tendered < total_amount:
        raise SalesOperationError(
            f"Amount tendered of {tendered} does not cover the "
            f"{total_amount} total."
        )
    return tendered, tendered - total_amount


def _configured_tax_rate():
    """The sales tax percentage to apply to a new Sale."""
    rate = getattr(settings, "SALES_TAX_RATE", Decimal("0"))
    return Decimal(rate).quantize(Decimal("0.01"))


def _normalize_items(items):
    try:
        submitted_items = list(items)
    except TypeError as exc:
        raise SalesOperationError("Add at least one Sale item") from exc

    if not submitted_items:
        raise SalesOperationError("Add at least one Sale item")

    normalized = []
    product_ids = set()
    for item in submitted_items:
        try:
            product_id = item["product_id"]
            quantity = item["quantity"]
        except (KeyError, TypeError) as exc:
            raise SalesOperationError("Invalid Sale item") from exc

        if (
            not isinstance(product_id, int)
            or isinstance(product_id, bool)
            or product_id <= 0
        ):
            raise SalesOperationError("Product is not available")
        if (
            not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity <= 0
        ):
            raise SalesOperationError("Quantity must be a positive whole number")
        if product_id in product_ids:
            raise SalesOperationError("Each product may appear only once in a Sale")

        discount = item.get("discount_amount", Decimal("0.00")) or Decimal("0.00")
        try:
            discount = Decimal(discount).quantize(Decimal("0.01"))
        except (ArithmeticError, TypeError, ValueError) as exc:
            raise SalesOperationError("Discount must be an amount") from exc
        if discount < 0:
            raise SalesOperationError("Discount cannot be negative")

        product_ids.add(product_id)
        normalized.append(
            {
                "product_id": product_id,
                "quantity": quantity,
                "discount_amount": discount,
            }
        )

    return sorted(normalized, key=lambda item: item["product_id"])


@transaction.atomic
def create_sale(
    *,
    customer_id,
    items,
    created_by,
    payment_method="",
    amount_tendered=None,
):
    normalized_items = _normalize_items(items)

    customer = None
    if customer_id is not None:
        try:
            customer = Customer.objects.select_for_update().get(
                pk=customer_id,
                is_active=True,
            )
        except Customer.DoesNotExist as exc:
            raise SalesOperationError("Customer is not available") from exc

    product_ids = [item["product_id"] for item in normalized_items]
    locked_products = list(
        Product.objects.select_for_update()
        .filter(pk__in=product_ids)
        .order_by("pk")
    )
    if len(locked_products) != len(product_ids):
        raise SalesOperationError("Product is not available")

    products_by_id = {product.pk: product for product in locked_products}
    prepared_items = []
    net_amount = Decimal("0.00")
    for item in normalized_items:
        product = products_by_id[item["product_id"]]
        quantity = item["quantity"]
        if not product.is_active:
            raise SalesOperationError("Product is not available")
        if quantity > product.current_stock:
            raise SalesOperationError(
                f"Only {product.current_stock} left of {product.name} "
                f"({product.sku}), but {quantity} were requested."
            )

        gross = product.selling_price * quantity
        discount = item["discount_amount"]
        if discount > gross:
            raise SalesOperationError(
                f"Discount of {discount} is more than the "
                f"{gross} line total for {product.name}."
            )
        subtotal = gross - discount
        prepared_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": product.selling_price,
                "discount_amount": discount,
                "subtotal": subtotal,
                # Snapshotted alongside price so margin on this Sale stays
                # correct after the Product is later repriced.
                "unit_cost": product.cost_price,
                "cost_subtotal": product.cost_price * quantity,
            }
        )
        net_amount += subtotal
        if net_amount > MAX_SALE_TOTAL:
            raise SalesOperationError("Sale total exceeds the supported maximum")

    # The rate is read once and stored on the Sale, so a later rate change
    # never rewrites tax that was already charged to a customer.
    tax_rate = _configured_tax_rate()
    tax_amount = (net_amount * tax_rate / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total_amount = net_amount + tax_amount
    if total_amount > MAX_SALE_TOTAL:
        raise SalesOperationError("Sale total exceeds the supported maximum")

    tendered, change = _resolve_payment(
        payment_method, amount_tendered, total_amount
    )

    sale = Sale.objects.create(
        customer=customer,
        customer_name=customer.name if customer else "",
        customer_address=customer.address if customer else "",
        net_amount=net_amount,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        tax_label=getattr(settings, "SALES_TAX_LABEL", "SST") if tax_rate else "",
        payment_method=payment_method or "",
        amount_tendered=tendered,
        change_given=change,
        total_amount=total_amount,
        created_by=created_by,
    )

    for item in prepared_items:
        product = item["product"]
        try:
            movement = stock_out(
                product_id=product.pk,
                quantity=item["quantity"],
                performed_by=created_by,
                reason=f"Sale {sale.sale_number}",
            )
        except InventoryOperationError as exc:
            raise SalesOperationError(str(exc)) from exc

        SaleItem.objects.create(
            sale=sale,
            product=product,
            stock_movement=movement,
            product_sku=product.sku,
            product_name=product.name,
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            discount_amount=item["discount_amount"],
            subtotal=item["subtotal"],
            unit_cost=item["unit_cost"],
            cost_subtotal=item["cost_subtotal"],
        )

    return sale


@transaction.atomic
def void_sale(*, sale_id, reason, voided_by):
    """Reverse a completed Sale, returning its stock.

    The Sale is not edited or deleted. A SaleReversal is recorded against it
    and the stock goes back, so the till record of what was rung up survives
    exactly as it was while the goods and the revenue are undone.
    """
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise SalesOperationError("A reason is required to void a Sale")

    try:
        sale = (
            Sale.objects.select_for_update()
            .prefetch_related("items__product")
            .get(pk=sale_id)
        )
    except Sale.DoesNotExist as exc:
        raise SalesOperationError("Sale is not available") from exc

    if hasattr(sale, "reversal"):
        raise SalesOperationError(f"{sale.sale_number} has already been voided")

    # An issued Invoice is a document the customer already holds. Undoing the
    # Sale behind it would leave that document describing a Sale that no
    # longer counts, so it needs a credit note rather than a void.
    if hasattr(sale, "invoice"):
        raise SalesOperationError(
            f"{sale.sale_number} has an issued Invoice and cannot be voided. "
            "Issue a credit note instead."
        )

    reversal = SaleReversal.objects.create(
        sale=sale,
        reason=normalized_reason,
        created_by=voided_by,
    )

    for item in sale.items.all():
        try:
            stock_in(
                product_id=item.product_id,
                quantity=item.quantity,
                performed_by=voided_by,
                reason=f"Void of {sale.sale_number}",
                # The Product may have been deactivated since it was sold;
                # the goods still come back.
                allow_inactive=True,
            )
        except InventoryOperationError as exc:
            raise SalesOperationError(str(exc)) from exc

    return reversal
