"""The shared public demo login.

The password is published on the login page and in the README on purpose, so
everything that account can reach has to be safe for a stranger to reach.
"""

from django.contrib.auth import get_user_model


DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"


def is_demo_account(user):
    return user.is_authenticated and user.get_username() == DEMO_USERNAME


def demo_credentials():
    """The demo login to advertise, or None where no demo account exists.

    Only seed_demo creates this account, so a deployment holding real records
    never shows a login hint.
    """
    exists = (
        get_user_model()
        .objects.filter(username=DEMO_USERNAME, is_active=True, is_superuser=False)
        .exists()
    )
    if not exists:
        return None
    return {"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
