from django.urls import path

from .views import InvoiceDetailView, InvoiceListView, IssueInvoiceView


app_name = "invoices"

urlpatterns = [
    path("", InvoiceListView.as_view(), name="list"),
    path("issue/<int:sale_pk>/", IssueInvoiceView.as_view(), name="issue"),
    path("<int:pk>/", InvoiceDetailView.as_view(), name="detail"),
]
