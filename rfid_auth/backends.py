from django.contrib.auth.backends import BaseBackend

from users.models import User


class RfidBackend(BaseBackend):
    """autentifikuje podla rfid_uid namiesto hesla.
    Pouziva sa cez django.contrib.auth.authenticate(request, rfid_uid=...)."""

    def authenticate(self, request, rfid_uid=None, **kwargs):
        if not rfid_uid:
            return None
        try:
            return User.objects.get(rfid_uid=rfid_uid, is_active=True)
        except User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None