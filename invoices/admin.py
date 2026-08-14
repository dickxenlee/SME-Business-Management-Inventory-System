from django.contrib import admin

from .models import Invoice, InvoiceItem


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    can_delete = False
    fields = (
        "product_sku",
        "product_name",
        "quantity",
        "unit_price",
        "subtotal",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in SAFE_METHODS

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number_display",
        "issued_at",
        "sale",
        "customer_name",
        "total_amount",
        "issued_by",
    )
    list_filter = ("issued_at",)
    search_fields = ("=id", "=sale__id", "customer_name")
    readonly_fields = (
        "invoice_number_display",
        "sale",
        "customer_name",
        "customer_address",
        "seller_name",
        "seller_address",
        "total_amount",
        "issued_by",
        "issued_at",
    )
    inlines = (InvoiceItemInline,)

    @admin.display(description="Invoice number")
    def invoice_number_display(self, invoice):
        return invoice.invoice_number

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and request.method in SAFE_METHODS

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "product_sku",
        "product_name",
        "quantity",
        "unit_price",
        "subtotal",
    )
    search_fields = ("=invoice__id", "product_sku", "product_name")
    readonly_fields = (
        "invoice",
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
