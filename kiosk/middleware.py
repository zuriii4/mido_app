from django.utils import timezone

from rfid_auth.models import KioskDevice, RfidSession


class RfidSessionMiddleware:
    """
    Dva typy autentifikacie:
    1. Kiosk device (X-Device-Token header alebo session['kiosk_device_token'])
    2. RFID user session (session['rfid_token'])
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Defaults
        request.kiosk_device = None
        request.rfid_session = None

        # === 1. Kiosk device token ===
        device_token = (
            request.headers.get('X-Device-Token')
            or request.session.get('kiosk_device_token')
        )
        if device_token:
            try:
                device = KioskDevice.objects.get(token=device_token, is_active=True)
                request.kiosk_device = device
                # Ak prisiel cez header, uloz do session pre dalsie requesty
                if request.headers.get('X-Device-Token') == device_token:
                    request.session['kiosk_device_token'] = device_token
                # Update last_seen
                device.last_seen_at = timezone.now()
                device.save(update_fields=['last_seen_at'])
            except KioskDevice.DoesNotExist:
                # Neplatny token - vymaz zo session
                if 'kiosk_device_token' in request.session:
                    del request.session['kiosk_device_token']

        # === 2. RFID user session ===
        rfid_token = request.session.get('rfid_token')
        if rfid_token:
            session = RfidSession.objects.filter(
                token=rfid_token,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).select_related('user').first()

            if session:
                request.rfid_session = session
                request.user = session.user

        return self.get_response(request)
