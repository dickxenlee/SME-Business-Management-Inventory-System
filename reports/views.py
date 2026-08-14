from django.views import View
from django.views.generic import TemplateView

from .csv_exports import inventory_movements_csv_response, sales_csv_response
from .forms import PeriodFilterForm
from .mixins import ReportsAccessMixin
from .services import (
    get_customer_metrics,
    get_inventory_report,
    get_invoice_metrics,
    get_sales_report,
    resolve_period,
)


def period_context(request):
    period = resolve_period(request.GET.get("period"))
    return period, PeriodFilterForm(initial={"period": period.key})


class ReportsView(ReportsAccessMixin, TemplateView):
    template_name = "reports/report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        period, period_form = period_context(self.request)
        sales = get_sales_report(period)
        context.update(
            {
                "period": period,
                "period_form": period_form,
                "sales_report": sales,
                "inventory_report": get_inventory_report(period, self.request.user),
                "customer_metrics": get_customer_metrics(period),
                "invoice_metrics": get_invoice_metrics(period),
                "top_products_chart": {
                    "labels": [
                        f'{row["product__sku"]} — {row["product__name"]}'
                        for row in sales["top_products_by_revenue"]
                    ],
                    "values": [
                        float(row["revenue"])
                        for row in sales["top_products_by_revenue"]
                    ],
                },
            }
        )
        return context


class SalesCsvView(ReportsAccessMixin, View):
    def get(self, request):
        return sales_csv_response(resolve_period(request.GET.get("period")))


class InventoryMovementsCsvView(ReportsAccessMixin, View):
    def get(self, request):
        return inventory_movements_csv_response(
            resolve_period(request.GET.get("period")),
            request.user,
        )
