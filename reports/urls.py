from django.urls import path

from .views import InventoryMovementsCsvView, ReportsView, SalesCsvView


app_name = "reports"

urlpatterns = [
    path("", ReportsView.as_view(), name="index"),
    path("sales.csv", SalesCsvView.as_view(), name="sales_csv"),
    path(
        "inventory-movements.csv",
        InventoryMovementsCsvView.as_view(),
        name="inventory_movements_csv",
    ),
]
