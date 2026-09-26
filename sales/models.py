from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    CARD = "CARD", "Card"
    EWALLET = "EWALLET", "E-wallet"
    TRANSFER = "TRANSFER", "Bank transfer"


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
    # net_amount is the taxable base and the figure reporting treats as
    # revenue. Tax is collected on the government's behalf, so folding it into
    # revenue would overstate both takings and gross profit.
    net_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    tax_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Snapshotted with the rate: Malaysia moved from GST to SST in 2018, and a
    # document reissued under a new label would misstate what was charged.
    tax_label = models.CharField(max_length=20, blank=True)
    # What the customer actually pays: net_amount + tax_amount.
    total_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Blank on Sales recorded before payment capture existed. Those are
    # reported as unrecorded rather than assumed to be cash.
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
    )
    # Only meaningful for cash: what the customer handed over, and what came
    # back. Null for card and e-wallet, where the exact amount is taken.
    amount_tendered = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    change_given = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        null=True,
        blank=True,
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
            ),
            models.CheckConstraint(
                condition=models.Q(net_amount__gte=0),
                name="sale_net_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="sale_tax_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_rate__gte=0),
                name="sale_tax_rate_nonnegative",
            ),
            # The three money columns must never drift apart in the database,
            # whatever writes them.
            models.CheckConstraint(
                condition=models.Q(
                    total_amount=models.F("net_amount") + models.F("tax_amount")
                ),
                name="sale_total_is_net_plus_tax",
            ),
            # Tendered and change are recorded together or not at all.
            models.CheckConstraint(
                condition=models.Q(
                    amount_tendered__isnull=True, change_given__isnull=True
                )
                | models.Q(
                    amount_tendered__isnull=False, change_given__isnull=False
                ),
                name="sale_cash_fields_recorded_together",
            ),
            models.CheckConstraint(
                condition=models.Q(change_given__isnull=True)
                | models.Q(
                    change_given=models.F("amount_tendered")
                    - models.F("total_amount")
                ),
                name="sale_change_is_tendered_less_total",
            ),
        ]

    @property
    def sale_number(self):
        return f"SALE-{self.pk:06d}" if self.pk is not None else "SALE-UNSAVED"

    @property
    def is_voided(self):
        return hasattr(self, "reversal")

    def __str__(self):
        return self.sale_number


class SaleReversal(models.Model):
    """A void of a completed Sale.

    The Sale itself is never edited or deleted: the business record of what
    was rung up stays exactly as it was, and this is a separate, later record
    that returns the stock and takes the Sale out of revenue.
    """

    sale = models.OneToOneField(
        Sale,
        on_delete=models.PROTECT,
        related_name="reversal",
    )
    reason = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="sale_reversals",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Void of {self.sale.sale_number}"


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
    discount_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Net of any line discount and before tax: unit_price * quantity
    # - discount_amount.
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
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="sale_item_discount_nonnegative",
            ),
            # A line can be discounted to zero but never below it, and the
            # stored subtotal must match the arithmetic it claims.
            models.CheckConstraint(
                condition=models.Q(
                    subtotal=models.F("unit_price") * models.F("quantity")
                    - models.F("discount_amount")
                ),
                name="sale_item_subtotal_matches_line_maths",
            ),
            models.UniqueConstraint(
                fields=("sale", "product"),
                name="unique_product_per_sale",
            ),
        ]

    def __str__(self):
        return f"{self.sale.sale_number} - {self.product_sku}"
