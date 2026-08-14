from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views
from .forms import BootstrapAuthenticationForm


app_name = "core"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path(
        "accounts/login/",
        LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=BootstrapAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        LogoutView.as_view(),
        name="logout",
    ),
]
