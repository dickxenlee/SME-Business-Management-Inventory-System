from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.models import Group


STAFF_GROUP_NAME = "Staff"


class BootstrapFormMixin:
    """Apply Bootstrap control classes without restating each field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class BootstrapAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    """Django's authentication form with presentation-only Bootstrap classes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Land the cursor in the first field so signing in needs no clicking.
        self.fields["username"].widget.attrs["autofocus"] = True
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["password"].widget.attrs["autocomplete"] = "current-password"


class BootstrapPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class BootstrapPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class BootstrapSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class StaffCreationForm(BootstrapFormMixin, UserCreationForm):
    """Create a staff account without going through Django admin.

    An email address is required rather than optional: without one the
    account can never use password reset, which would put the owner back in
    the shell every time somebody forgets their password.
    """

    email = forms.EmailField(
        required=True,
        help_text="Used for password resets, so it must be reachable.",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Another account already uses this email address."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # Staff run the shop, never Django admin: is_staff stays off so the
        # admin site remains superuser-only.
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            group, _ = Group.objects.get_or_create(name=STAFF_GROUP_NAME)
            user.groups.add(group)
        return user


class StaffSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    """Used by an owner to set a password for someone who is locked out."""
