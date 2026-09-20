from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Upper


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    current_stock = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "sku"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(selling_price__gte=0),
                name="product_selling_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(cost_price__gte=0),
                name="product_cost_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(current_stock__gte=0),
                name="product_current_stock_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(low_stock_threshold__gte=0),
                name="product_low_stock_threshold_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(sku=Upper("sku")),
                name="product_sku_uppercase",
            ),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"

    @staticmethod
    def normalize_sku(value):
        return value.strip().upper() if value else value

    def clean(self):
        self.sku = self.normalize_sku(self.sku)
        super().clean()

    def save(self, *args, **kwargs):
        self.sku = self.normalize_sku(self.sku)
        return super().save(*args, **kwargs)

    @property
    def margin_rate(self):
        """Current gross margin percentage, or None when it cannot be read.

        This is the margin the Product would earn if sold today. Margin
        actually earned on past Sales comes from each SaleItem's own cost
        snapshot, not from here.
        """
        if not self.selling_price:
            return None
        return (
            (self.selling_price - self.cost_price)
            * Decimal("100.00")
            / self.selling_price
        ).quantize(Decimal("0.1"))

    @property
    def is_low_stock(self):
        return (
            self.is_active
            and self.current_stock > 0
            and self.current_stock <= self.low_stock_threshold
        )

    @property
    def is_out_of_stock(self):
        return self.is_active and self.current_stock == 0

