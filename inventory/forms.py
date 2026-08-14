from django import forms

from products.models import Product

from .services import MAX_STOCK_QUANTITY


class InventoryOperationForm(forms.Form):
    product = forms.ModelChoiceField(queryset=Product.objects.none())
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name", "sku")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(
                field.widget, forms.Select
            ) else "form-control"


class StockQuantityForm(InventoryOperationForm):
    quantity = forms.IntegerField(min_value=1, max_value=MAX_STOCK_QUANTITY)

    field_order = ("product", "quantity", "reason")


class StockInForm(StockQuantityForm):
    pass


class StockOutForm(StockQuantityForm):
    pass


class StockAdjustmentForm(InventoryOperationForm):
    new_stock = forms.IntegerField(
        min_value=0,
        max_value=MAX_STOCK_QUANTITY,
        label="Final stock quantity",
    )
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Explain why the recorded stock is being corrected.",
    )

    field_order = ("product", "new_stock", "reason")
