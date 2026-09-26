from django.urls import path

from .views import (
    SaleCreateView,
    SaleDetailView,
    SaleListView,
    VoidSaleView,
)


app_name = "sales"

urlpatterns = [
    path("", SaleListView.as_view(), name="list"),
    path("create/", SaleCreateView.as_view(), name="create"),
    path("<int:pk>/", SaleDetailView.as_view(), name="detail"),
    path("<int:pk>/void/", VoidSaleView.as_view(), name="void"),
]
