from rest_framework.permissions import BasePermission

from rfid_auth.models import KioskDevice


class IsKioskDevice(BasePermission):
    """Povoli len poziadavky autentifikovane cez KioskDeviceAuthentication (X-Device-Token)."""

    def has_permission(self, request, view):
        return isinstance(request.auth, KioskDevice)
