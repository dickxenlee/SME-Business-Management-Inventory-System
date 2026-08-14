from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


phone_validator = RegexValidator(
    regex=r"^\+?(?=(?:\D*\d){7,15}\D*$)[0-9 ()-]+$",
    message=(
        "Enter a valid phone number using digits, spaces, hyphens, "
        "parentheses, and an optional leading +."
    ),
)


class Customer(models.Model):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]

    def __str__(self):
        return self.name

    def clean(self):
        self.name = self.name.strip()
        self.phone = self.phone.strip()
        self.email = self.email.strip()
        self.address = self.address.strip()
        super().clean()
        if not self.name:
            raise ValidationError({"name": "Customer name is required."})
