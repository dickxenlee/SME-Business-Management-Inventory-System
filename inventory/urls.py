from django.urls import path

from .views import (
    StockAdjustmentView,
    StockInView,
    StockMovementListView,
    StockOutView,
)


app_name = "inventory"

urlpatterns = [
    path("", StockMovementListView.as_view(), name="history"),
    path("stock-in/", StockInView.as_view(), name="stock_in"),
    path("stock-out/", StockOutView.as_view(), name="stock_out"),
    path("adjustment/", StockAdjustmentView.as_view(), name="adjustment"),
]
