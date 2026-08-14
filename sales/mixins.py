from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class SalesAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Allow Sales access to superusers and members of the Staff group."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or user.groups.filter(name="Staff").exists()
