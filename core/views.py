from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render


def is_admin_or_staff(user):
    """Return whether a user holds an approved internal application role."""
    return user.is_superuser or user.groups.filter(name="Staff").exists()


@login_required
def home(request):
    """Render the application's dashboard placeholder."""
    if not is_admin_or_staff(request.user):
        raise PermissionDenied
    return render(request, "core/home.html")
