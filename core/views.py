from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from reports.forms import PeriodFilterForm
from reports.services import get_dashboard_data, resolve_period


def is_admin_or_staff(user):
    """Return whether a user holds an approved internal application role."""
    return user.is_superuser or user.groups.filter(name="Staff").exists()


@login_required
def home(request):
    """Render the authenticated business dashboard."""
    if not is_admin_or_staff(request.user):
        raise PermissionDenied
    period = resolve_period(request.GET.get("period"))
    dashboard = get_dashboard_data(period, request.user)
    dashboard["revenue_chart"] = {
        "labels": [row["date"].isoformat() for row in dashboard["daily_revenue"]],
        "values": [float(row["revenue"]) for row in dashboard["daily_revenue"]],
    }
    return render(
        request,
        "core/home.html",
        {
            "period": period,
            "period_form": PeriodFilterForm(initial={"period": period.key}),
            "dashboard": dashboard,
        },
    )
