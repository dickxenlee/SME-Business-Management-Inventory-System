from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_safe
from django.views.generic import FormView, ListView

from reports.forms import PeriodFilterForm
from reports.services import get_dashboard_data, resolve_period

from .forms import StaffCreationForm, StaffSetPasswordForm


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
        # "21 Sep" reads on a crowded axis; an ISO date does not. Built from
        # parts rather than strftime, whose no-pad flag is platform specific.
        "labels": [
            f"{row['date'].day} {row['date']:%b}"
            for row in dashboard["daily_revenue"]
        ],
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


class PasswordResetStartView(auth_views.PasswordResetView):
    """Password reset, but only where a reset email can actually be sent.

    With no mail host configured the built-in view would accept the form and
    report success while delivering nothing, so staff would sit waiting for an
    email that was never going to arrive.
    """

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "PASSWORD_RESET_ENABLED", False):
            raise Http404("Password reset is not configured")
        return super().dispatch(request, *args, **kwargs)


class OwnerOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Staff administration is the owner's job, not a shop duty."""

    def test_func(self):
        return self.request.user.is_superuser


class StaffListView(OwnerOnlyMixin, ListView):
    template_name = "core/staff_list.html"
    context_object_name = "staff_members"

    def get_queryset(self):
        return (
            get_user_model()
            .objects.prefetch_related("groups")
            .order_by("-is_active", "username")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["password_reset_enabled"] = getattr(
            settings, "PASSWORD_RESET_ENABLED", False
        )
        return context


class StaffCreateView(OwnerOnlyMixin, FormView):
    template_name = "core/staff_form.html"
    form_class = StaffCreationForm
    success_url = reverse_lazy("core:staff_list")

    def form_valid(self, form):
        user = form.save()
        messages.success(
            self.request,
            f"{user.username} can now sign in and was added to Staff.",
        )
        return super().form_valid(form)


class StaffSetPasswordView(OwnerOnlyMixin, FormView):
    template_name = "core/staff_set_password.html"
    form_class = StaffSetPasswordForm
    success_url = reverse_lazy("core:staff_list")

    def get_target(self):
        return get_object_or_404(get_user_model(), pk=self.kwargs["pk"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.get_target()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["target"] = self.get_target()
        return context

    def form_valid(self, form):
        target = form.save()
        messages.success(
            self.request,
            f"A new password was set for {target.username}.",
        )
        return super().form_valid(form)


class StaffToggleAccessView(OwnerOnlyMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        target = get_object_or_404(get_user_model(), pk=pk)

        # Locking yourself out would leave the shop with no owner account and
        # no way back in short of the command line.
        if target.pk == request.user.pk:
            messages.error(request, "You cannot remove your own access.")
            return redirect("core:staff_list")

        # No separate "last owner" check is needed: only an active owner can
        # reach this view and they cannot target themselves, so suspending
        # anyone else always leaves at least the person doing it.

        # Accounts are disabled, never deleted: Sales, Invoices and stock
        # movements all point at who did them.
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        messages.success(
            request,
            f"{target.username} was "
            f"{'given access' if target.is_active else 'suspended'}.",
        )
        return redirect("core:staff_list")
