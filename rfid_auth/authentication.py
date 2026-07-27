from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from rfid_auth.models import KioskDevice, RfidSession


class KioskDeviceAuthentication(BaseAuthentication):
    """Autentifikuje kiosk  cez hlavicku X-Device-Token.
    Vracia (None, device) - request.user zostava AnonymousUser, request.auth = device."""

    def authenticate(self, request):
        token = request.headers.get('X-Device-Token')
        if not token:
            return None
        try:
            device = KioskDevice.objects.get(token=token, is_active=True)
        except KioskDevice.DoesNotExist:
            raise AuthenticationFailed('Neplatny alebo neaktivny kiosk token.')
        device.last_seen_at = timezone.now()
        device.save(update_fields=['last_seen_at'])
        return (None, device)


class RfidSessionAuthentication(BaseAuthentication):
    """Autentifikuje pouzivatela cez 'Authorization: Bearer <token>' vydany pri RFID prihlaseni."""

    keyword = 'Bearer'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith(f'{self.keyword} '):
            return None
        token = auth_header[len(self.keyword) + 1:].strip()
        if not token:
            return None

        try:
            session = RfidSession.objects.select_related('user').get(token=token)
        except RfidSession.DoesNotExist:
            raise AuthenticationFailed('Neplatna session.')

        if not session.is_valid():
            raise AuthenticationFailed('Session expirovala alebo bola odhlasena.')
        if not session.user.is_active:
            raise AuthenticationFailed('Pouzivatel je neaktivny.')

        return (session.user, session)
