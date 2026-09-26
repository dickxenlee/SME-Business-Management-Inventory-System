from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import (
    BootstrapAuthenticationForm,
    BootstrapPasswordChangeForm,
    BootstrapPasswordResetForm,
    BootstrapSetPasswordForm,
)


app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=BootstrapAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            form_class=BootstrapPasswordChangeForm,
            success_url=reverse_lazy("core:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "accounts/password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
    # The reset flow is only routed when email can actually deliver the link.
    # Registering it regardless would give staff a form that appears to work
    # and then quietly never sends anything.
    path(
        "accounts/password-reset/",
        views.PasswordResetStartView.as_view(
            template_name="registration/password_reset_form.html",
            form_class=BootstrapPasswordResetForm,
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("core:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            form_class=BootstrapSetPasswordForm,
            success_url=reverse_lazy("core:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/password-reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
    path("staff/", views.StaffListView.as_view(), name="staff_list"),
    path("staff/add/", views.StaffCreateView.as_view(), name="staff_create"),
    path(
        "staff/<int:pk>/password/",
        views.StaffSetPasswordView.as_view(),
        name="staff_set_password",
    ),
    path(
        "staff/<int:pk>/access/",
        views.StaffToggleAccessView.as_view(),
        name="staff_toggle_access",
    ),
]
