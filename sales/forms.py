from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory

from customers.models import Customer
from inventory.services import MAX_STOCK_QUANTITY
from products.models import Product


class SaleForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(),
        required=False,
        empty_label="Walk-in Customer",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(
            is_active=True
        ).order_by("name", "pk")
        self.fields["customer"].widget.attrs["class"] = "form-select"


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product):
        return (
            f"{product.sku} - {product.name} | "
            f"RM {product.selling_price:.2f} | Stock: {product.current_stock}"
        )


class SaleItemForm(forms.Form):
    product = ProductChoiceField(queryset=Product.objects.none())
    quantity = forms.IntegerField(min_value=1, max_value=MAX_STOCK_QUANTITY)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name", "sku")
        self.fields["product"].widget.attrs["class"] = "form-select"
        self.fields["quantity"].widget.attrs["class"] = "form-control"


class BaseSaleItemFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return

        product_ids = set()
        item_count = 0
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            product = form.cleaned_data.get("product")
            if product is None:
                continue
            item_count += 1
            if product.pk in product_ids:
                raise ValidationError("Each product may appear only once in a Sale.")
            product_ids.add(product.pk)

        if item_count == 0:
            raise ValidationError("Add at least one Sale item.")


SaleItemFormSet = formset_factory(
    SaleItemForm,
    formset=BaseSaleItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
