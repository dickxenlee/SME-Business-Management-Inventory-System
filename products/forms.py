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
            "low_stock_threshold",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_sku(self):
        return Product.normalize_sku(self.cleaned_data["sku"])

    def save(self, commit=True):
        """Save Product metadata without writing a stale stock value."""
        is_new = self.instance._state.adding
        product = super().save(commit=False)
        if not commit:
            return product

        if is_new:
            product.save()
        else:
            product.save(update_fields=(*self.Meta.fields, "updated_at"))
        self.save_m2m()
        return product
