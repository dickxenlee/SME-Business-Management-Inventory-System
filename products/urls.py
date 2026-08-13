from django.urls import path

from .views import (
    ProductCreateView,
    ProductDeactivateView,
    ProductDetailView,
    ProductListView,
    ProductUpdateView,
)


app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("create/", ProductCreateView.as_view(), name="create"),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="edit"),
    path(
        "<int:pk>/deactivate/",
        ProductDeactivateView.as_view(),
        name="deactivate",
    ),
]

