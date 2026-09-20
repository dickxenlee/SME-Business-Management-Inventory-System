from decimal import Decimal

from django.db import transaction

from customers.models import Customer
from inventory.services import InventoryOperationError, stock_out
from products.models import Product

from .models import Sale, SaleItem


MAX_SALE_TOTAL = Decimal("9999999999999999999999.99")


class SalesOperationError(Exception):
    """Raised when a Sale cannot be completed without violating a rule."""


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

        product_ids.add(product_id)
        normalized.append({"product_id": product_id, "quantity": quantity})

    return sorted(normalized, key=lambda item: item["product_id"])


@transaction.atomic
def create_sale(*, customer_id, items, created_by):
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
    total_amount = Decimal("0.00")
    for item in normalized_items:
        product = products_by_id[item["product_id"]]
        quantity = item["quantity"]
        if not product.is_active:
            raise SalesOperationError("Product is not available")
        if quantity > product.current_stock:
            raise SalesOperationError(f"Insufficient stock for {product.sku}")

        subtotal = product.selling_price * quantity
        prepared_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": product.selling_price,
                "subtotal": subtotal,
                # Snapshotted alongside price so margin on this Sale stays
                # correct after the Product is later repriced.
                "unit_cost": product.cost_price,
                "cost_subtotal": product.cost_price * quantity,
            }
        )
        total_amount += subtotal
        if total_amount > MAX_SALE_TOTAL:
            raise SalesOperationError("Sale total exceeds the supported maximum")

    sale = Sale.objects.create(
        customer=customer,
        customer_name=customer.name if customer else "",
        customer_address=customer.address if customer else "",
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
            subtotal=item["subtotal"],
            unit_cost=item["unit_cost"],
            cost_subtotal=item["cost_subtotal"],
        )

    return sale
