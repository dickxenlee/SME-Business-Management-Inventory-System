"""Root URL configuration for SME Manager."""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("", include("core.urls")),
    path("products/", include("products.urls")),
    path("inventory/", include("inventory.urls")),
    path("customers/", include("customers.urls")),
    path("sales/", include("sales.urls")),
    path("invoices/", include("invoices.urls")),
    path("admin/", admin.site.urls),
]
