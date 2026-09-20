from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Sale(models.Model):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales",
        null=True,
        blank=True,
    )
    customer_name = models.CharField(max_length=255, blank=True)
    customer_address = models.TextField(blank=True)
    total_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sales_created",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="sale_total_amount_nonnegative",
            )
        ]

    @property
    def sale_number(self):
        return f"SALE-{self.pk:06d}" if self.pk is not None else "SALE-UNSAVED"

    def __str__(self):
        return self.sale_number


class SaleItem(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sale_items",
    )
    stock_movement = models.OneToOneField(
        "inventory.StockMovement",
        on_delete=models.PROTECT,
        related_name="sale_item",
    )
    product_sku = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    subtotal = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Cost is snapshotted like price so historical margin survives later
    # Product repricing. Null on SaleItems recorded before cost capture
    # existed; those Sales are reported as cost-unknown rather than guessed.
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    cost_subtotal = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="sale_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__isnull=True)
                | models.Q(unit_cost__gte=0),
                name="sale_item_unit_cost_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_subtotal__isnull=True)
                | models.Q(cost_subtotal__gte=0),
                name="sale_item_cost_subtotal_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    unit_cost__isnull=True, cost_subtotal__isnull=True
                )
                | models.Q(
                    unit_cost__isnull=False, cost_subtotal__isnull=False
                ),
                name="sale_item_cost_snapshot_complete",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="sale_item_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="sale_item_subtotal_nonnegative",
            ),
            models.UniqueConstraint(
                fields=("sale", "product"),
                name="unique_product_per_sale",
            ),
        ]

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product_sku}"
