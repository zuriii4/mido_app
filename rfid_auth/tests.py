from datetime import timedelta

from django.contrib.auth import authenticate
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from rfid_auth.authentication import KioskDeviceAuthentication, RfidSessionAuthentication
from rfid_auth.backends import RfidBackend
from rfid_auth.models import KioskDevice, RfidSession
from users.models import User


def make_user(**kwargs):
    defaults = {
        'username': 'jnovak',
        'firstname': 'Jan',
        'lastname': 'Novak',
        'rfid_uid': 'RFID-001',
        'external_id': 'EXT-001',
    }
    defaults.update(kwargs)
    return User.objects.create(**defaults)


class KioskDeviceModelTests(TestCase):
    def test_save_generates_token_when_missing(self):
        device = KioskDevice.objects.create(name='Vrátnica')
        self.assertTrue(device.token)
        self.assertEqual(len(device.token), 64)

    def test_save_keeps_explicit_token(self):
        device = KioskDevice.objects.create(name='Vrátnica', token='fixed-token')
        self.assertEqual(device.token, 'fixed-token')


class RfidSessionModelTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.device = KioskDevice.objects.create(name='Kiosk 1')

    def test_save_generates_token_when_missing(self):
        session = RfidSession.objects.create(
            user=self.user,
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertTrue(session.token)

    def test_is_valid_true_for_fresh_session(self):
        session = RfidSession.objects.create(
            user=self.user,
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        self.assertTrue(session.is_valid())

    def test_is_valid_false_when_expired(self):
        session = RfidSession.objects.create(
            user=self.user,
            device=self.device,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(session.is_valid())

    def test_is_valid_false_when_revoked(self):
        session = RfidSession.objects.create(
            user=self.user,
            device=self.device,
            expires_at=timezone.now() + timedelta(minutes=10),
            revoked_at=timezone.now(),
        )
        self.assertFalse(session.is_valid())


class RfidBackendTests(TestCase):
    def setUp(self):
        self.backend = RfidBackend()
        self.user = make_user()

    def test_authenticate_returns_none_without_rfid_uid(self):
        self.assertIsNone(self.backend.authenticate(None))

    def test_authenticate_returns_user_for_matching_active_uid(self):
        result = self.backend.authenticate(None, rfid_uid='RFID-001')
        self.assertEqual(result, self.user)

    def test_authenticate_returns_none_for_unknown_uid(self):
        self.assertIsNone(self.backend.authenticate(None, rfid_uid='does-not-exist'))

    def test_authenticate_returns_none_for_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(self.backend.authenticate(None, rfid_uid='RFID-001'))

    def test_via_django_authenticate_entrypoint(self):
        result = authenticate(rfid_uid='RFID-001')
        self.assertEqual(result, self.user)

    def test_get_user_returns_active_user(self):
        self.assertEqual(self.backend.get_user(self.user.pk), self.user)

    def test_get_user_returns_none_for_inactive_user(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertIsNone(self.backend.get_user(self.user.pk))


class KioskDeviceAuthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.auth = KioskDeviceAuthentication()
        self.device = KioskDevice.objects.create(name='Kiosk 1')

    def test_returns_none_without_header(self):
        request = self.factory.post('/api/auth/rfid-login/')
        self.assertIsNone(self.auth.authenticate(request))

    def test_valid_token_returns_device_and_updates_last_seen(self):
        self.assertIsNone(self.device.last_seen_at)
        request = self.factory.post(
            '/api/auth/rfid-login/', HTTP_X_DEVICE_TOKEN=self.device.token
        )
        user, device = self.auth.authenticate(request)
        self.assertIsNone(user)
        self.assertEqual(device, self.device)
        self.device.refresh_from_db()
        self.assertIsNotNone(self.device.last_seen_at)

    def test_unknown_token_raises(self):
        request = self.factory.post('/api/auth/rfid-login/', HTTP_X_DEVICE_TOKEN='bogus')
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_inactive_device_token_raises(self):
        self.device.is_active = False
        self.device.save(update_fields=['is_active'])
        request = self.factory.post(
            '/api/auth/rfid-login/', HTTP_X_DEVICE_TOKEN=self.device.token
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class RfidSessionAuthenticationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.auth = RfidSessionAuthentication()
        self.user = make_user()
        self.session = RfidSession.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_returns_none_without_header(self):
        request = self.factory.post('/api/auth/logout/')
        self.assertIsNone(self.auth.authenticate(request))

    def test_returns_none_for_wrong_scheme(self):
        request = self.factory.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Token {self.session.token}'
        )
        self.assertIsNone(self.auth.authenticate(request))

    def test_valid_token_returns_user_and_session(self):
        request = self.factory.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        user, session = self.auth.authenticate(request)
        self.assertEqual(user, self.user)
        self.assertEqual(session, self.session)

    def test_unknown_token_raises(self):
        request = self.factory.post('/api/auth/logout/', HTTP_AUTHORIZATION='Bearer bogus')
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_expired_session_raises(self):
        self.session.expires_at = timezone.now() - timedelta(seconds=1)
        self.session.save(update_fields=['expires_at'])
        request = self.factory.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_revoked_session_raises(self):
        self.session.revoked_at = timezone.now()
        self.session.save(update_fields=['revoked_at'])
        request = self.factory.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    def test_inactive_user_raises(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        request = self.factory.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class RfidLoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.device = KioskDevice.objects.create(name='Kiosk 1')
        self.user = make_user()

    def test_login_without_device_token_is_rejected(self):
        response = self.client.post('/api/auth/rfid-login/', {'rfid_uid': 'RFID-001'})
        self.assertIn(response.status_code, (401, 403))

    def test_login_with_valid_card_creates_session(self):
        response = self.client.post(
            '/api/auth/rfid-login/',
            {'rfid_uid': 'RFID-001'},
            HTTP_X_DEVICE_TOKEN=self.device.token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['rfid_uid'], 'RFID-001')
        self.assertEqual(RfidSession.objects.count(), 1)
        session = RfidSession.objects.get()
        self.assertEqual(session.device, self.device)
        self.assertEqual(session.user, self.user)

    def test_login_revokes_previous_active_session(self):
        # existujuca este platna session
        old = RfidSession.objects.create(
            user=self.user, device=self.device,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(
            '/api/auth/rfid-login/',
            {'rfid_uid': 'RFID-001'},
            HTTP_X_DEVICE_TOKEN=self.device.token,
        )
        self.assertEqual(response.status_code, 201)
        old.refresh_from_db()
        self.assertIsNotNone(old.revoked_at)  # stara session revokovana
        active = RfidSession.objects.filter(user=self.user, revoked_at__isnull=True)
        self.assertEqual(active.count(), 1)  # len nova ostala aktivna

    def test_login_with_unknown_card_returns_404(self):
        response = self.client.post(
            '/api/auth/rfid-login/',
            {'rfid_uid': 'does-not-exist'},
            HTTP_X_DEVICE_TOKEN=self.device.token,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(RfidSession.objects.count(), 0)

    def test_login_with_invalid_device_token_is_rejected(self):
        response = self.client.post(
            '/api/auth/rfid-login/',
            {'rfid_uid': 'RFID-001'},
            HTTP_X_DEVICE_TOKEN='bogus',
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(RfidSession.objects.count(), 0)


class RfidLogoutViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.session = RfidSession.objects.create(
            user=self.user,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_logout_without_token_is_rejected(self):
        response = self.client.post('/api/auth/logout/')
        self.assertIn(response.status_code, (401, 403))

    def test_logout_revokes_session(self):
        response = self.client.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        self.assertEqual(response.status_code, 204)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)

    def test_logout_twice_is_rejected_second_time(self):
        self.client.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        response = self.client.post(
            '/api/auth/logout/', HTTP_AUTHORIZATION=f'Bearer {self.session.token}'
        )
        self.assertIn(response.status_code, (401, 403))
