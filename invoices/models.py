from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Invoice(models.Model):
    sale = models.OneToOneField(
        "sales.Sale",
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    customer_name = models.CharField(max_length=255, blank=True)
    customer_address = models.TextField(blank=True)
    seller_name = models.CharField(max_length=255)
    seller_address = models.TextField()
    total_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="invoices_issued",
        null=True,
        blank=True,
    )
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-issued_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="invoice_total_amount_nonnegative",
            )
        ]

    @property
    def invoice_number(self):
        return f"INV-{self.pk:06d}" if self.pk is not None else "INV-UNSAVED"

    def __str__(self):
        return self.invoice_number


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
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

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="invoice_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="invoice_item_unit_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="invoice_item_subtotal_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.product_sku}"
