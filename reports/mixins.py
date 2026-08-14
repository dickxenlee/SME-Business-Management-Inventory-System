from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ReportsAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow reporting access to superusers and Staff group members."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Staff").exists()
