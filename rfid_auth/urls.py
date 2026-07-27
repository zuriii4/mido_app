from django.urls import path

from rfid_auth.views import RfidLoginView, RfidLogoutView

urlpatterns = [
    path('rfid-login/', RfidLoginView.as_view(), name='rfid-login'),
    path('logout/', RfidLogoutView.as_view(), name='rfid-logout'),
]
