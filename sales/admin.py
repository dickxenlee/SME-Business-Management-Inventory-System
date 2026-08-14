from django.contrib import admin

from .models import Sale, SaleItem


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    can_delete = False
    fields = (
        "product",
        "product_sku",
        "product_name",
        "quantity",
        "unit_price",
        "subtotal",
        "stock_movement",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in SAFE_METHODS

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        "sale_number_display",
        "created_at",
        "customer_name",
        "total_amount",
        "created_by",
    )
    list_filter = ("created_at",)
    search_fields = ("customer_name",)
    readonly_fields = (
        "sale_number_display",
        "customer",
        "customer_name",
        "customer_address",
        "total_amount",
        "created_by",
        "created_at",
    )
    inlines = (SaleItemInline,)

    @admin.display(description="Sale number")
    def sale_number_display(self, sale):
        return sale.sale_number

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in SAFE_METHODS

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "product_sku",
        "product_name",
        "quantity",
        "unit_price",
        "subtotal",
    )
    search_fields = ("=sale__id", "product_sku", "product_name")
    readonly_fields = (
        "sale",
        "product",
        "stock_movement",
        "product_sku",
        "product_name",
        "quantity",
        "unit_price",
        "subtotal",
    )

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in SAFE_METHODS

    def has_delete_permission(self, request, obj=None):
        return False
