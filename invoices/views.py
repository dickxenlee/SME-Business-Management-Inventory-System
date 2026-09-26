from datetime import date

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView

from .mixins import InvoicesAccessMixin
from .models import CreditNote, Invoice
from .services import (
    CreditNoteOperationError,
    InvoiceOperationError,
    issue_credit_note,
    issue_invoice,
)


def _derived_pk_from_query(query, prefix):
    normalized = query.strip().upper()
    if not normalized.startswith(prefix):
        return None
    number = normalized[len(prefix) :]
    return int(number) if number.isdigit() else None


class InvoiceListView(InvoicesAccessMixin, ListView):
    model = Invoice
    template_name = "invoices/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().select_related("sale", "issued_by")
        self.query = self.request.GET.get("q", "").strip()
        self.issue_date = self.request.GET.get("date", "").strip()

        if self.query:
            query_filter = Q(customer_name__icontains=self.query)
            if invoice_pk := _derived_pk_from_query(self.query, "INV-"):
                query_filter |= Q(pk=invoice_pk)
            if sale_pk := _derived_pk_from_query(self.query, "SALE-"):
                query_filter |= Q(sale_id=sale_pk)
            queryset = queryset.filter(query_filter)

        if self.issue_date:
            try:
                parsed_date = date.fromisoformat(self.issue_date)
            except ValueError:
                self.issue_date = ""
            else:
                queryset = queryset.filter(issued_at__date=parsed_date)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        context["selected_date"] = self.issue_date
        return context


class InvoiceDetailView(InvoicesAccessMixin, DetailView):
    model = Invoice
    template_name = "invoices/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("sale", "issued_by")
            .prefetch_related("items")
        )


class IssueInvoiceView(InvoicesAccessMixin, View):
    http_method_names = ["post"]

    def post(self, request, sale_pk):
        try:
            invoice = issue_invoice(sale_id=sale_pk, issued_by=request.user)
        except InvoiceOperationError as exc:
            messages.error(request, str(exc))
            return redirect("sales:detail", pk=sale_pk)

        messages.success(request, f"{invoice.invoice_number} was issued.")
        return redirect("invoices:detail", pk=invoice.pk)


class CreditNoteForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        label="Why is this Invoice being credited?",
        help_text="Printed on the credit note and kept permanently.",
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("A reason is required.")
        return reason


class OwnerOnlyMixin(InvoicesAccessMixin):
    """Crediting moves stock and money, so it is the owner's call."""

    def test_func(self):
        return self.request.user.is_superuser


class IssueCreditNoteView(OwnerOnlyMixin, View):
    template_name = "invoices/credit_note_form.html"

    def get_invoice(self, pk):
        return get_object_or_404(
            Invoice.objects.select_related("sale", "credit_note"), pk=pk
        )

    def get(self, request, pk):
        invoice = self.get_invoice(pk)
        return render(
            request,
            self.template_name,
            {"invoice": invoice, "form": CreditNoteForm()},
        )

    def post(self, request, pk):
        invoice = self.get_invoice(pk)
        form = CreditNoteForm(request.POST)
        if form.is_valid():
            try:
                credit_note = issue_credit_note(
                    invoice_id=invoice.pk,
                    reason=form.cleaned_data["reason"],
                    issued_by=request.user,
                )
            except CreditNoteOperationError as exc:
                form.add_error(None, str(exc))
            else:
                messages.success(
                    request,
                    f"{credit_note.credit_note_number} was issued and the "
                    "stock returned.",
                )
                return redirect("invoices:credit_note_detail", pk=credit_note.pk)
        return render(
            request, self.template_name, {"invoice": invoice, "form": form}
        )


class CreditNoteDetailView(InvoicesAccessMixin, DetailView):
    model = CreditNote
    template_name = "invoices/credit_note_detail.html"
    context_object_name = "credit_note"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("invoice__sale", "issued_by")
            .prefetch_related("items")
        )
