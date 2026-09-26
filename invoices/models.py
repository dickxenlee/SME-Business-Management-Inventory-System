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
    # Copied from the Sale so the document keeps the figures it was issued
    # with, whatever the tax rate becomes later.
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
            ),
            models.CheckConstraint(
                condition=models.Q(net_amount__gte=0),
                name="invoice_net_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="invoice_tax_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_amount=models.F("net_amount") + models.F("tax_amount")
                ),
                name="invoice_total_is_net_plus_tax",
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
    discount_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=Decimal("0.00"),
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
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="invoice_item_discount_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.product_sku}"


class CreditNote(models.Model):
    """A document that cancels an issued Invoice.

    Neither the Invoice nor the Sale behind it is edited. The customer holds
    the original document, so the correction has to be its own numbered
    document that references it, and both stay on file.
    """

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        related_name="credit_note",
    )
    reason = models.TextField()
    # Copied from the Invoice, for the same reason the Invoice copies from the
    # Sale: the document must keep the figures it was issued with.
    customer_name = models.CharField(max_length=255, blank=True)
    customer_address = models.TextField(blank=True)
    seller_name = models.CharField(max_length=255)
    seller_address = models.TextField()
    net_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
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
    tax_label = models.CharField(max_length=20, blank=True)
    total_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="credit_notes_issued",
        null=True,
        blank=True,
    )
    issued_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-issued_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_amount__gte=0),
                name="credit_note_total_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(net_amount__gte=0),
                name="credit_note_net_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_amount__gte=0),
                name="credit_note_tax_amount_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total_amount=models.F("net_amount") + models.F("tax_amount")
                ),
                name="credit_note_total_is_net_plus_tax",
            ),
        ]

    @property
    def credit_note_number(self):
        return f"CN-{self.pk:06d}" if self.pk is not None else "CN-UNSAVED"

    def __str__(self):
        return self.credit_note_number


class CreditNoteItem(models.Model):
    credit_note = models.ForeignKey(
        CreditNote,
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
    discount_amount = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=Decimal("0.00"),
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
                name="credit_note_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="credit_note_item_subtotal_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.credit_note.credit_note_number} - {self.product_sku}"
