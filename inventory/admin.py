from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "product",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "performed_by",
    )
    list_filter = ("movement_type", "created_at")
    search_fields = ("product__sku", "product__name", "reason", "performed_by__username")
    readonly_fields = (
        "product",
        "movement_type",
        "quantity",
        "previous_stock",
        "new_stock",
        "reason",
        "performed_by",
        "created_at",
    )

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in {
            "GET",
            "HEAD",
            "OPTIONS",
        }

    def has_delete_permission(self, request, obj=None):
        return False
