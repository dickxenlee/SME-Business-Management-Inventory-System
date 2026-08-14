from django.contrib import messages
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import FormView, ListView

from .forms import StockAdjustmentForm, StockInForm, StockOutForm
from .mixins import InventoryAdminAccessMixin, InventoryReadAccessMixin
from .models import StockMovement
from .services import InventoryOperationError, adjust_stock, stock_in, stock_out


class StockMovementListView(InventoryReadAccessMixin, ListView):
    model = StockMovement
    template_name = "inventory/movement_list.html"
    context_object_name = "stock_movements"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("product", "performed_by")
        if not self.request.user.is_superuser:
            queryset = queryset.filter(product__is_active=True)

        self.query = self.request.GET.get("q", "").strip()
        self.movement_type = self.request.GET.get("movement_type", "").strip()
        if self.query:
            queryset = queryset.filter(
                Q(product__sku__icontains=self.query)
                | Q(product__name__icontains=self.query)
            )
        if self.movement_type in StockMovement.MovementType.values:
            queryset = queryset.filter(movement_type=self.movement_type)
        else:
            self.movement_type = ""
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        context["selected_movement_type"] = self.movement_type
        context["movement_types"] = StockMovement.MovementType.choices
        return context


class InventoryOperationView(InventoryReadAccessMixin, FormView):
    template_name = "inventory/movement_form.html"
    success_url = reverse_lazy("inventory:history")
    page_title = "Inventory operation"
    submit_label = "Save movement"
    operation = None

    def get_initial(self):
        initial = super().get_initial()
        if product_id := self.request.GET.get("product"):
            initial["product"] = product_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = self.page_title
        context["submit_label"] = self.submit_label
        return context

    def get_operation_kwargs(self, form):
        return {
            "product_id": form.cleaned_data["product"].pk,
            "quantity": form.cleaned_data["quantity"],
            "performed_by": self.request.user,
            "reason": form.cleaned_data["reason"],
        }
    def form_valid(self, form):
        try:
            movement = self.operation(**self.get_operation_kwargs(form))
        except InventoryOperationError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"{movement.get_movement_type_display()} recorded for {movement.product}.",
        )
        return super().form_valid(form)


class StockInView(InventoryOperationView):
    form_class = StockInForm
    operation = staticmethod(stock_in)
    page_title = "Stock In"
    submit_label = "Record Stock In"


class StockOutView(InventoryOperationView):
    form_class = StockOutForm
    operation = staticmethod(stock_out)
    page_title = "Stock Out"
    submit_label = "Record Stock Out"


class StockAdjustmentView(InventoryAdminAccessMixin, InventoryOperationView):
    form_class = StockAdjustmentForm
    operation = staticmethod(adjust_stock)
    page_title = "Stock Adjustment"
    submit_label = "Record Adjustment"

    def get_operation_kwargs(self, form):
        return {
            "product_id": form.cleaned_data["product"].pk,
            "new_stock": form.cleaned_data["new_stock"],
            "performed_by": self.request.user,
            "reason": form.cleaned_data["reason"],
        }
