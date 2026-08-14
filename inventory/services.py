from django.db import transaction

from products.models import Product

from .models import StockMovement


MAX_STOCK_QUANTITY = 2_147_483_647


class InventoryOperationError(Exception):
    """Raised when a requested inventory operation violates a business rule."""


def _positive_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


@transaction.atomic
def _change_stock(
    *,
    product_id,
    movement_type,
    performed_by,
    reason="",
    quantity=None,
    desired_stock=None,
):
    try:
        product = Product.objects.select_for_update().get(pk=product_id)
    except Product.DoesNotExist as exc:
        raise InventoryOperationError("Product not found") from exc

    if not product.is_active:
        raise InventoryOperationError(
            "Inactive products cannot receive stock movements"
        )

    previous_stock = product.current_stock
    normalized_reason = reason.strip()

    if movement_type == StockMovement.MovementType.STOCK_IN:
        if not _positive_integer(quantity):
            raise InventoryOperationError("Quantity must be a positive whole number")
        if quantity > MAX_STOCK_QUANTITY:
            raise InventoryOperationError("Quantity exceeds the supported maximum")
        new_stock = previous_stock + quantity
        if new_stock > MAX_STOCK_QUANTITY:
            raise InventoryOperationError(
                "Resulting stock exceeds the supported maximum"
            )
    elif movement_type == StockMovement.MovementType.STOCK_OUT:
        if not _positive_integer(quantity):
            raise InventoryOperationError("Quantity must be a positive whole number")
        if quantity > MAX_STOCK_QUANTITY:
            raise InventoryOperationError("Quantity exceeds the supported maximum")
        if quantity > previous_stock:
            raise InventoryOperationError("Insufficient stock")
        new_stock = previous_stock - quantity
    else:
        if not _nonnegative_integer(desired_stock):
            raise InventoryOperationError(
                "Final stock must be a non-negative whole number"
            )
        if desired_stock > MAX_STOCK_QUANTITY:
            raise InventoryOperationError("Final stock exceeds the supported maximum")
        if not normalized_reason:
            raise InventoryOperationError(
                "A reason is required for stock adjustments"
            )
        if desired_stock == previous_stock:
            raise InventoryOperationError("Adjustment must change the stock level")
        new_stock = desired_stock
        quantity = abs(previous_stock - new_stock)

    product.current_stock = new_stock
    product.save(update_fields=["current_stock", "updated_at"])
    return StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        previous_stock=previous_stock,
        new_stock=new_stock,
        reason=normalized_reason,
        performed_by=performed_by,
    )


def stock_in(*, product_id, quantity, performed_by, reason=""):
    return _change_stock(
        product_id=product_id,
        movement_type=StockMovement.MovementType.STOCK_IN,
        quantity=quantity,
        performed_by=performed_by,
        reason=reason,
    )


def stock_out(*, product_id, quantity, performed_by, reason=""):
    return _change_stock(
        product_id=product_id,
        movement_type=StockMovement.MovementType.STOCK_OUT,
        quantity=quantity,
        performed_by=performed_by,
        reason=reason,
    )


def adjust_stock(*, product_id, new_stock, performed_by, reason):
    return _change_stock(
        product_id=product_id,
        movement_type=StockMovement.MovementType.ADJUSTMENT,
        desired_stock=new_stock,
        performed_by=performed_by,
        reason=reason,
    )
