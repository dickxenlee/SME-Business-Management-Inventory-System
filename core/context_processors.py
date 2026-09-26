"""Template context shared across the whole site."""

from django.conf import settings


def account_features(request):
    """Expose whether password reset can actually deliver an email.

    The login page must not offer a "Forgot your password?" link when there is
    no mail host, because the flow would accept the request and send nothing.
    """
    return {
        "password_reset_enabled": getattr(
            settings, "PASSWORD_RESET_ENABLED", False
        ),
    }
