from django.contrib.auth.forms import AuthenticationForm


class BootstrapAuthenticationForm(AuthenticationForm):
    """Django's authentication form with presentation-only Bootstrap classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        # Land the cursor in the first field so signing in needs no clicking.
        self.fields["username"].widget.attrs["autofocus"] = True
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"

