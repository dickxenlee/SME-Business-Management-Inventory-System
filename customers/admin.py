from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "phone", "email")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        """Customers are deactivated instead of physically deleted."""
        return False
