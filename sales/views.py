from datetime import date

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import SaleForm, SaleItemFormSet
from .mixins import SalesAccessMixin
from .models import Sale
from .services import SalesOperationError, create_sale


def _sale_pk_from_query(query):
    normalized = query.strip().upper()
    if normalized.startswith("SALE-"):
        normalized = normalized[5:]
    return int(normalized) if normalized.isdigit() else None


class SaleListView(SalesAccessMixin, ListView):
    model = Sale
    template_name = "sales/sale_list.html"
    context_object_name = "sales"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("customer", "created_by")
        self.query = self.request.GET.get("q", "").strip()
        self.sale_date = self.request.GET.get("date", "").strip()

        if self.query:
            query_filter = Q(customer_name__icontains=self.query)
            if sale_pk := _sale_pk_from_query(self.query):
                query_filter |= Q(pk=sale_pk)
            queryset = queryset.filter(query_filter)

        if self.sale_date:
            try:
                parsed_date = date.fromisoformat(self.sale_date)
            except ValueError:
                self.sale_date = ""
            else:
                queryset = queryset.filter(created_at__date=parsed_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        context["selected_date"] = self.sale_date
        return context


class SaleDetailView(SalesAccessMixin, DetailView):
    model = Sale
    template_name = "sales/sale_detail.html"
    context_object_name = "sale"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("customer", "created_by", "invoice")
            .prefetch_related(
                "items__product",
                "items__stock_movement",
            )
        )


class SaleCreateView(SalesAccessMixin, View):
    template_name = "sales/sale_form.html"

    def get(self, request):
        return self.render_forms(request, SaleForm(), SaleItemFormSet(prefix="items"))

    def post(self, request):
        sale_form = SaleForm(request.POST)
        item_formset = SaleItemFormSet(request.POST, prefix="items")
        sale_error = ""

        if sale_form.is_valid() and item_formset.is_valid():
            customer = sale_form.cleaned_data["customer"]
            items = [
                {
                    "product_id": form.cleaned_data["product"].pk,
                    "quantity": form.cleaned_data["quantity"],
                    "discount_amount": form.cleaned_data.get("discount_amount"),
                }
                for form in item_formset.forms
                if form.cleaned_data
                and not form.cleaned_data.get("DELETE", False)
                and form.cleaned_data.get("product") is not None
            ]
            try:
                sale = create_sale(
                    customer_id=customer.pk if customer else None,
                    items=items,
                    created_by=request.user,
                )
            except SalesOperationError as exc:
                sale_error = str(exc)
            else:
                messages.success(request, f"{sale.sale_number} was completed.")
                return redirect("sales:detail", pk=sale.pk)

        return self.render_forms(request, sale_form, item_formset, sale_error)

    def render_forms(self, request, sale_form, item_formset, sale_error=""):
        return render(
            request,
            self.template_name,
            {
                "form": sale_form,
                "item_formset": item_formset,
                "sale_error": sale_error,
                # The form previews tax so staff can read the real total back
                # to the customer; the Sale itself is priced on the server.
                "sales_tax_rate": getattr(settings, "SALES_TAX_RATE", 0),
                "sales_tax_label": getattr(settings, "SALES_TAX_LABEL", "SST"),
            },
        )
