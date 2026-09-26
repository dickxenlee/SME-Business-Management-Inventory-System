from django.urls import path

from .views import (
    CreditNoteDetailView,
    InvoiceDetailView,
    InvoiceListView,
    IssueCreditNoteView,
    IssueInvoiceView,
)


app_name = "invoices"

urlpatterns = [
    path("", InvoiceListView.as_view(), name="list"),
    path("issue/<int:sale_pk>/", IssueInvoiceView.as_view(), name="issue"),
    path("<int:pk>/", InvoiceDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/credit/",
        IssueCreditNoteView.as_view(),
        name="issue_credit_note",
    ),
    path(
        "credit-notes/<int:pk>/",
        CreditNoteDetailView.as_view(),
        name="credit_note_detail",
    ),
]
