from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ProductReadAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow Product reads to superusers and members of the Staff group."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Staff").exists()


class ProductAdminAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict Product mutations to Django superusers."""

    def test_func(self):
        return self.request.user.is_superuser

