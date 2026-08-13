from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "sku",
            "name",
            "selling_price",
            "cost_price",
            "current_stock",
            "low_stock_threshold",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_sku(self):
        return Product.normalize_sku(self.cleaned_data["sku"])

