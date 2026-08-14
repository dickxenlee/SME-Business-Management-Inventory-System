from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import CustomerForm
from .mixins import CustomerAccessMixin, CustomerAdminAccessMixin
from .models import Customer


class CustomerListView(CustomerAccessMixin, ListView):
    model = Customer
    template_name = "customers/customer_list.html"
    context_object_name = "customers"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)

        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            queryset = queryset.filter(
                Q(name__icontains=self.query)
                | Q(phone__icontains=self.query)
                | Q(email__icontains=self.query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        return context


class CustomerDetailView(CustomerAccessMixin, DetailView):
    model = Customer
    template_name = "customers/customer_detail.html"
    context_object_name = "customer"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)
        return queryset


class CustomerCreateView(CustomerAccessMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def get_success_url(self):
        return reverse("customers:detail", args=[self.object.pk])


class CustomerUpdateView(CustomerAccessMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = "customers/customer_form.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_success_url(self):
        return reverse("customers:detail", args=[self.object.pk])


class CustomerDeactivateView(CustomerAdminAccessMixin, View):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        if customer.is_active:
            customer.is_active = False
            customer.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"{customer.name} was deactivated.")
        return redirect("customers:list")
