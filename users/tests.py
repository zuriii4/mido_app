from django.test import TestCase
from rest_framework.test import APIClient

from core.testutils import auth_client, make_user
from rfid_auth.models import KioskDevice
from users.models import BusinessUnit, ProfessionCategory, User


class MeViewTests(TestCase):
    def test_me_requires_auth(self):
        response = APIClient().get('/api/users/me/')
        self.assertIn(response.status_code, (401, 403))

    def test_me_returns_own_profile(self):
        user = make_user()
        response = auth_client(user).get('/api/users/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], user.username)
        self.assertEqual(response.data['rfid_uid'], user.rfid_uid)


class UserAdminApiTests(TestCase):
    def setUp(self):
        self.staff = make_user(is_staff=True)
        self.staff_client = auth_client(self.staff)
        self.worker = make_user()
        self.worker_client = auth_client(self.worker)

    def test_list_is_staff_only(self):
        self.assertEqual(self.worker_client.get('/api/users/').status_code, 403)
        self.assertEqual(self.staff_client.get('/api/users/').status_code, 200)

    def test_list_returns_users(self):
        response = self.staff_client.get('/api/users/')
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn(self.worker.username, usernames)

    def test_search_by_username(self):
        response = self.staff_client.get(f'/api/users/?search={self.worker.username}')
        usernames = [u['username'] for u in response.data['results']]
        self.assertEqual(usernames, [self.worker.username])

    def test_filter_by_is_active(self):
        inactive = make_user(is_active=False)
        response = self.staff_client.get('/api/users/?is_active=false')
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn(inactive.username, usernames)
        self.assertNotIn(self.worker.username, usernames)

    def test_filter_by_business_unit(self):
        bu = BusinessUnit.objects.create(code='ZVAR')
        bu_user = make_user(business_unit=bu)
        response = self.staff_client.get('/api/users/?business_unit__code=ZVAR')
        usernames = [u['username'] for u in response.data['results']]
        self.assertEqual(usernames, [bu_user.username])

    def test_create_user(self):
        bu = BusinessUnit.objects.create(code='MONT')
        pc = ProfessionCategory.objects.create(name='Zvaracka')
        response = self.staff_client.post('/api/users/', {
            'username': 'novy1',
            'firstname': 'Novy',
            'lastname': 'Clovek',
            'external_id': 'HR-999',
            'rfid_uid': 'CARD-NEW',
            'business_unit': 'MONT',
            'profession_category': 'Zvaracka',
        })
        self.assertEqual(response.status_code, 201, response.data)
        created = User.objects.get(username='novy1')
        self.assertEqual(created.rfid_uid, 'CARD-NEW')
        self.assertEqual(created.business_unit, bu)
        self.assertEqual(created.profession_code, pc)

    def test_create_is_staff_only(self):
        response = self.worker_client.post('/api/users/', {
            'username': 'x', 'firstname': 'a', 'lastname': 'b', 'external_id': 'HR-X',
        })
        self.assertEqual(response.status_code, 403)

    def test_assign_card_via_patch(self):
        user = make_user(rfid_uid=None)
        response = self.staff_client.patch(
            f'/api/users/{user.pk}/', {'rfid_uid': 'CARD-ASSIGNED'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertEqual(user.rfid_uid, 'CARD-ASSIGNED')

    def test_blank_rfid_becomes_null(self):
        user = make_user()
        response = self.staff_client.patch(
            f'/api/users/{user.pk}/', {'rfid_uid': ''}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertIsNone(user.rfid_uid)

    def test_duplicate_card_rejected(self):
        existing = make_user(rfid_uid='CARD-DUP')
        user = make_user(rfid_uid=None)
        response = self.staff_client.patch(
            f'/api/users/{user.pk}/', {'rfid_uid': 'CARD-DUP'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertIsNone(user.rfid_uid)
        self.assertEqual(existing.rfid_uid, 'CARD-DUP')

    def test_deactivate_via_patch(self):
        user = make_user()
        response = self.staff_client.patch(
            f'/api/users/{user.pk}/', {'is_active': False}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_put_not_allowed(self):
        user = make_user()
        response = self.staff_client.put(
            f'/api/users/{user.pk}/', {'username': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, 405)


class CodelistApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)
        self.bu = BusinessUnit.objects.create(code='ZVAR')
        self.pc = ProfessionCategory.objects.create(name='Zvaracka')

    def test_business_units_require_auth(self):
        self.assertIn(APIClient().get('/api/users/business-units/').status_code, (401, 403))

    def test_business_units_list(self):
        response = self.client.get('/api/users/business-units/')
        self.assertEqual(response.status_code, 200)
        codes = [b['code'] for b in response.data['results']]
        self.assertIn('ZVAR', codes)

    def test_profession_categories_list(self):
        response = self.client.get('/api/users/profession-categories/')
        self.assertEqual(response.status_code, 200)
        names = [p['name'] for p in response.data['results']]
        self.assertIn('Zvaracka', names)


class AdminRegistrationTests(TestCase):
    def test_core_models_registered_in_admin(self):
        from django.contrib import admin
        self.assertIn(User, admin.site._registry)
        self.assertIn(BusinessUnit, admin.site._registry)
        self.assertIn(ProfessionCategory, admin.site._registry)


class LoginThrottleTests(TestCase):
    def test_login_endpoint_has_throttle_scope(self):
        from rfid_auth.views import RfidLoginView
        self.assertEqual(RfidLoginView.throttle_scope, 'rfid_login')


class CleanupSessionsCommandTests(TestCase):
    def test_cleanup_removes_old_invalid_sessions(self):
        from django.core.management import call_command
        from django.utils import timezone

        from rfid_auth.models import RfidSession

        device = KioskDevice.objects.create(name='K1')
        user = make_user()
        old_expired = RfidSession.objects.create(
            user=user, device=device,
            expires_at=timezone.now() - timezone.timedelta(days=30),
        )
        valid = RfidSession.objects.create(
            user=user, device=device,
            expires_at=timezone.now() + timezone.timedelta(minutes=10),
        )

        call_command('cleanup_sessions', '--days', '7')

        self.assertFalse(RfidSession.objects.filter(pk=old_expired.pk).exists())
        self.assertTrue(RfidSession.objects.filter(pk=valid.pk).exists())
