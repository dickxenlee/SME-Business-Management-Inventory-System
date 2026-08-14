from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_safe

from reports.forms import PeriodFilterForm
from reports.services import get_dashboard_data, resolve_period


def is_admin_or_staff(user):
    """Return whether a user holds an approved internal application role."""
    return user.is_superuser or user.groups.filter(name="Staff").exists()


@require_safe
def health(request):
    """Report application readiness without exposing operational details."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        response = JsonResponse({"status": "unavailable"}, status=503)
    else:
        response = JsonResponse({"status": "ok"})
    response["Cache-Control"] = "no-store"
    return response


def csrf_failure(request, reason=""):
    """Render a generic CSRF rejection without disclosing diagnostics."""
    return render(request, "403_csrf.html", status=403)


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
