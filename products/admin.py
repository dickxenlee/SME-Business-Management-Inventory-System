from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "selling_price",
        "current_stock",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("sku", "name")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        """Products are deactivated instead of physically deleted."""
        return False
