from django.shortcuts import render


def home(request):
    """Render the application's dashboard placeholder."""
    return render(request, "core/home.html")

