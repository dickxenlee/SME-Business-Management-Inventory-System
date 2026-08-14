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
    readonly_fields = ("current_stock", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        """Products are deactivated instead of physically deleted."""
        return False

    def save_model(self, request, obj, form, change):
        """Save metadata without allowing stale admin state to replace stock."""
        if not change:
            return super().save_model(request, obj, form, change)
        obj.save(
            update_fields=(
                "sku",
                "name",
                "selling_price",
                "cost_price",
                "low_stock_threshold",
                "is_active",
                "updated_at",
            )
        )
