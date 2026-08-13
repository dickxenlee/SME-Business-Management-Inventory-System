from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import ProductForm
from .mixins import ProductAdminAccessMixin, ProductReadAccessMixin
from .models import Product


class ProductListView(ProductReadAccessMixin, ListView):
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)

        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            queryset = queryset.filter(
                Q(sku__icontains=self.query) | Q(name__icontains=self.query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        return context


class ProductDetailView(ProductReadAccessMixin, DetailView):
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            queryset = queryset.filter(is_active=True)
        return queryset


class ProductCreateView(ProductAdminAccessMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def get_success_url(self):
        return reverse("products:detail", args=[self.object.pk])


class ProductUpdateView(ProductAdminAccessMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def get_success_url(self):
        return reverse("products:detail", args=[self.object.pk])


class ProductDeactivateView(ProductAdminAccessMixin, View):
    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.is_active:
            product.is_active = False
            product.save(update_fields=["is_active", "updated_at"])
            messages.success(request, f"{product.name} was deactivated.")
        return redirect("products:list")

