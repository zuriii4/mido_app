from django.shortcuts import render


def home(request):
    """Uvodna obrazovka kiosku."""
    return render(request, 'kiosk/home.html')
