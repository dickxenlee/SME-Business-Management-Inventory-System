from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class InventoryReadAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow inventory access to superusers and members of the Staff group."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Staff").exists()


class InventoryAdminAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict stock adjustments to Django superusers."""

    def test_func(self):
        return self.request.user.is_superuser
