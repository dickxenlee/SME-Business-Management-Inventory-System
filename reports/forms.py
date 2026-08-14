from django import forms

from .services import PERIOD_CHOICES


class PeriodFilterForm(forms.Form):
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.Select(attrs={"class": "form-select", "aria-label": "Reporting period"}),
    )
