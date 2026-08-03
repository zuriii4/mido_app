from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth import authenticate
from django.urls import reverse
from django.views import View

from rfid_auth.models import KioskDevice, RfidSession
from django.conf import settings
from django.utils import timezone
from documents.services import get_unsigned_documents


class KioskView(View):
    """Homepage kiosku — GET zobrazi formular, POST spracuje RFID login."""

    template_name = 'kiosk/home.html'

    def get(self, request):
        if not request.kiosk_device:
            return redirect('kiosk:device-setup')
        return render(request, self.template_name)

    # Validacia UID
    MIN_UID_LEN = 4
    MAX_UID_LEN = 32
    import re
    UID_PATTERN = re.compile(r'^[A-Za-z0-9]+$')

    def _htmx_error(self, message, code=400):
        """Vrati HTML odpoved pre HTMX (aby sa zobrazila chyba v #login-status)."""
        return HttpResponse(
            f'<div class="alert alert-danger">{message}</div>',
            status=200,  
        )

    def _htmx_redirect(self, url):
        """HTMX redirect cez hlavicku."""
        response = HttpResponse(status=200)
        response['HX-Redirect'] = url
        return response

    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)

        rfid_uid = request.POST.get('rfid_uid', '').strip()
        is_htmx = request.headers.get('HX-Request') == 'true'

        # Device kontrola
        if not request.kiosk_device:
            if is_htmx:
                return HttpResponse('<div class="alert alert-danger">Chýba device token.</div>', status=200)
            return redirect('kiosk:device-setup')

        # === Validacia ===
        if not rfid_uid:
            if is_htmx:
                return self._htmx_error('Prázdne UID.')
            messages.error(request, 'Zadajte RFID UID.')
            return render(request, self.template_name)

        if len(rfid_uid) < self.MIN_UID_LEN or len(rfid_uid) > self.MAX_UID_LEN:
            logger.warning(f'kiosk login: UID mimo rozsah (len={len(rfid_uid)})')
            if is_htmx:
                return self._htmx_error(f'UID musí mať {self.MIN_UID_LEN}–{self.MAX_UID_LEN} znakov.')
            messages.error(request, 'Neplatné UID.')
            return render(request, self.template_name)

        if not self.UID_PATTERN.match(rfid_uid):
            logger.warning(f'kiosk login: UID s nepovolenymi znakmi')
            if is_htmx:
                return self._htmx_error('UID obsahuje nepovolené znaky.')
            messages.error(request, 'Neplatné UID.')
            return render(request, self.template_name)

        # Normalizacia (uppercase hex)
        rfid_uid = rfid_uid.upper()

        # === Auth ===
        user = authenticate(request, rfid_uid=rfid_uid)
        if user is None:
            logger.info(f'kiosk login: neznama karta UID={rfid_uid[:4]}*** (ip={self._client_ip(request)})')
            if is_htmx:
                return self._htmx_error('Neznáma alebo neaktívna karta.')
            messages.error(request, 'Neznáma alebo neaktívna RFID karta.')
            return render(request, self.template_name)

        if not user.is_active:
            logger.warning(f'kiosk login: neaktivny user uid={user.id}')
            if is_htmx:
                return self._htmx_error('Účet je deaktivovaný.')
            messages.error(request, 'Účet je deaktivovaný.')
            return render(request, self.template_name)

        # === Revoke + nova session ===
        RfidSession.objects.filter(
            user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()
        ).update(revoked_at=timezone.now())

        session = RfidSession.objects.create(
            user=user,
            device=request.kiosk_device,
            expires_at=timezone.now() + settings.RFID_SESSION_TTL,
        )
        request.session['rfid_token'] = session.token
        request.session.set_expiry(settings.RFID_SESSION_TTL.total_seconds())

        logger.info(f'kiosk login OK: user={user.username}')

        if is_htmx:
            return self._htmx_redirect(reverse('kiosk:dashboard'))
        return redirect('kiosk:dashboard')

    @staticmethod
    def _client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '?')



class DeviceSetupView(View):
    """
    GET - zobrazi formular pre zadanie kiosk device token
    POST - overi token, ulozi do session, vrati success alebo chybu
    """

    def get(self, request):
        # Ak uz mame validny device, preskoc na home
        if request.kiosk_device:
            return redirect('kiosk:home')
        return render(request, 'kiosk/device_setup.html')

    def post(self, request):
        token = request.POST.get('device_token', '').strip()
        is_htmx = request.headers.get('HX-Request') == 'true'

        if not token:
            return self._error('Zadajte device token.', is_htmx)

        if len(token) < 32:
            return self._error('Token je príliš krátky.', is_htmx)

        try:
            device = KioskDevice.objects.get(token=token, is_active=True)
        except KioskDevice.DoesNotExist:
            return self._error('Neplatný alebo neaktívny device token.', is_htmx)

        # OK - uloz do session
        request.session['kiosk_device_token'] = device.token
        device.last_seen_at = timezone.now()
        device.save(update_fields=['last_seen_at'])

        if is_htmx:
            response = HttpResponse(
                '<div class="alert alert-success">Token prijatý. Načítavam...</div>',
                status=200,
            )
            response['HX-Redirect'] = '/kiosk/'
            return response
        return redirect('kiosk:home')

    def _error(self, message, is_htmx):
        if is_htmx:
            return HttpResponse(
                f'<div class="alert alert-danger">{message}</div>',
                status=200,  # 200 aby HTMX swapol
            )
        return JsonResponse({'error': message}, status=400)

class DashboardView(View):
    """Dashboard prihlaseneho usera."""

    template_name = 'kiosk/dashboard.html'

    def get(self, request):
        documents = get_unsigned_documents(request.user)
        return render(request, self.template_name, {'documents': documents})


def document_detail(request, pk):
    """Detail dokumentu na podpisanie."""
    return render(request, 'kiosk/document_detail.html', {'document_pk': pk})


class LogoutView(View):
    """Odhlasi RFID usera (zachova device token - ten je per-device, nie per-user)."""

    def get(self, request):
        device_token = request.session.get('kiosk_device_token')

        rfid_session = request.rfid_session
        if rfid_session and not rfid_session.revoked_at:
            rfid_session.revoked_at = timezone.now()
            rfid_session.save(update_fields=['revoked_at'])

        for key in ['rfid_token', '_auth_user_id', '_auth_user_backend', '_auth_user_hash']:
            if key in request.session:
                del request.session[key]


        if device_token:
            request.session['kiosk_device_token'] = device_token

        messages.success(request, 'Boli ste odhlásení.')
        return redirect('kiosk:home')
