from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory
from django.forms.formsets import DELETION_FIELD_NAME

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


class ProductSelect(forms.Select):
    """Carries price and stock per option so the form can total itself.

    Out-of-stock Products stay listed but are disabled: hiding them makes
    staff think the Product was deleted, while leaving them selectable only
    produces a rejection after a full round-trip.
    """

    def create_option(self, name, value, label, selected, index, **kwargs):
        option = super().create_option(
            name, value, label, selected, index, **kwargs
        )
        product = getattr(value, "instance", None)
        if product is not None:
            option["attrs"]["data-price"] = f"{product.selling_price:.2f}"
            option["attrs"]["data-stock"] = product.current_stock
            option["attrs"]["data-name"] = product.name
            if product.current_stock == 0:
                option["attrs"]["disabled"] = True
        return option


class ProductChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, product):
        if product.current_stock == 0:
            availability = "Out of stock"
        else:
            availability = f"{product.current_stock} in stock"
        return (
            f"{product.name} ({product.sku}) - "
            f"RM {product.selling_price:.2f} - {availability}"
        )


class SaleItemForm(forms.Form):
    product = ProductChoiceField(
        queryset=Product.objects.none(),
        widget=ProductSelect,
    )
    quantity = forms.IntegerField(min_value=1, max_value=MAX_STOCK_QUANTITY)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(
            is_active=True
        ).order_by("name", "sku")
        self.fields["product"].widget.attrs["class"] = "form-select"
        self.fields["quantity"].widget.attrs.update(
            {"class": "form-control", "inputmode": "numeric", "min": 1}
        )

    def clean(self):
        cleaned = super().clean()
        product = cleaned.get("product")
        quantity = cleaned.get("quantity")
        # Catch the stock problem on the offending field rather than letting it
        # surface as a whole-form banner naming only a SKU.
        if product is not None and quantity is not None:
            if product.current_stock == 0:
                self.add_error(
                    "product",
                    f"{product.name} is out of stock.",
                )
            elif quantity > product.current_stock:
                self.add_error(
                    "quantity",
                    f"Only {product.current_stock} left of {product.name}.",
                )
        return cleaned


class BaseSaleItemFormSet(BaseFormSet):
    def add_fields(self, form, index):
        """Present the deletion flag as a visible, reversible control."""
        super().add_fields(form, index)
        if DELETION_FIELD_NAME in form.fields:
            delete_field = form.fields[DELETION_FIELD_NAME]
            delete_field.label = "Removed"
            delete_field.widget.attrs["class"] = "form-check-input"

    def _is_deleted(self, form):
        return self.can_delete and self._should_delete_form(form)

    def clean(self):
        super().clean()
        # Forms marked for deletion are excluded from is_valid(), so their
        # errors must not suppress the checks below either.
        if any(form.errors for form in self.forms if not self._is_deleted(form)):
            return

        product_ids = set()
        item_count = 0
        for form in self.forms:
            if self._is_deleted(form):
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
