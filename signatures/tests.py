import shutil
import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.testutils import auth_client, make_assignment, make_document, make_session, make_user
from documents.models import DocumentAssignment, DocumentVersion
from rfid_auth.models import KioskDevice
from signatures.models import Signature
from users.models import BusinessUnit

MEDIA_ROOT = tempfile.mkdtemp(prefix='mido_signatures_tests_')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SignApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.device = KioskDevice.objects.create(name='Kiosk 1')
        self.user = make_user()
        self.client = auth_client(self.user, device=self.device)
        self.document = make_document(with_file=True)
        self.version = self.document.current_version

    def sign(self, client=None, version_id=None, rfid_uid=None):
        return (client or self.client).post('/api/signatures/sign/', {
            'document_version_id': str(version_id or self.version.pk),
            'rfid_uid': rfid_uid if rfid_uid is not None else self.user.rfid_uid,
        })

    def test_sign_requires_auth(self):
        response = APIClient().post('/api/signatures/sign/', {})
        self.assertIn(response.status_code, (401, 403))

    def test_sign_happy_path(self):
        response = self.sign()
        self.assertEqual(response.status_code, 201)
        signature = Signature.objects.get()
        self.assertEqual(signature.user, self.user)
        self.assertEqual(signature.document_version, self.version)
        self.assertEqual(signature.rfid_uid_used, self.user.rfid_uid)
        self.assertEqual(signature.device_id, 'Kiosk 1')  # z RfidSession.device

    def test_signed_document_disappears_from_unsigned(self):
        list_before = self.client.get('/api/documents/?unsigned=true')
        self.assertEqual(len(list_before.data['results']), 1)

        self.sign()

        list_after = self.client.get('/api/documents/?unsigned=true')
        self.assertEqual(len(list_after.data['results']), 0)

    def test_rfid_mismatch_returns_403_without_record(self):
        response = self.sign(rfid_uid='CUDZIA-KARTA')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Signature.objects.count(), 0)

    def test_duplicate_signature_returns_409(self):
        self.sign()
        response = self.sign()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Signature.objects.count(), 1)

    def test_non_current_version_returns_400(self):
        DocumentVersion.objects.filter(pk=self.version.pk).update(is_current=False)
        new_version = DocumentVersion.objects.create(
            document=self.document, version_label='A', is_current=True
        )
        new_version.file_path.save('vA.pdf', ContentFile(b'%PDF-1.4 v2'), save=True)

        response = self.sign(version_id=self.version.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Signature.objects.count(), 0)

    def test_invisible_document_returns_400(self):
        other_bu = BusinessUnit.objects.create(code='INA-BU')
        hidden = make_document(with_file=True)
        make_assignment(hidden, DocumentAssignment.TARGET_BUSINESS_UNIT,
                        business_units=[other_bu])
        response = self.sign(version_id=hidden.current_version.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Signature.objects.count(), 0)

    def test_inactive_document_returns_400(self):
        self.document.is_active = False
        self.document.save(update_fields=['is_active'])
        response = self.sign()
        self.assertEqual(response.status_code, 400)

    def test_unknown_version_returns_404(self):
        response = self.sign(version_id='00000000-0000-0000-0000-000000000000')
        self.assertEqual(response.status_code, 404)

    def test_mine_lists_only_own_signatures(self):
        self.sign()
        other = make_user()
        Signature.objects.create(user=other, document_version=self.version)

        response = self.client.get('/api/signatures/mine/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['document_title'], self.document.title)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SignatureReportsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.staff = make_user(is_staff=True)
        self.staff_client = auth_client(self.staff)
        self.worker = make_user()
        self.worker_client = auth_client(self.worker)
        self.document = make_document(with_file=True)
        self.version = self.document.current_version

    def test_reports_are_staff_only(self):
        for url in (
            f'/api/signatures/reports/document/{self.document.pk}/',
            f'/api/signatures/reports/unsigned/?document_id={self.document.pk}',
        ):
            response = self.worker_client.get(url)
            self.assertEqual(response.status_code, 403, url)

    def test_document_report_lists_signatures(self):
        Signature.objects.create(
            user=self.worker, document_version=self.version, rfid_uid_used=self.worker.rfid_uid
        )
        response = self.staff_client.get(f'/api/signatures/reports/document/{self.document.pk}/')
        self.assertEqual(response.status_code, 200)
        rows = response.data['results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['username'], self.worker.username)
        self.assertEqual(rows[0]['rfid_uid_used'], self.worker.rfid_uid)

    def test_unsigned_report_requires_document_id(self):
        response = self.staff_client.get('/api/signatures/reports/unsigned/')
        self.assertEqual(response.status_code, 400)

    def test_unsigned_report_lists_users_without_signature(self):
        signed_user = make_user()
        Signature.objects.create(user=signed_user, document_version=self.version)

        response = self.staff_client.get(
            f'/api/signatures/reports/unsigned/?document_id={self.document.pk}'
        )
        self.assertEqual(response.status_code, 200)
        usernames = [u['username'] for u in response.data['results']]
        self.assertIn(self.worker.username, usernames)
        self.assertNotIn(signed_user.username, usernames)

    def test_unsigned_report_business_unit_filter(self):
        bu = BusinessUnit.objects.create(code='FILTER-BU')
        bu_user = make_user(business_unit=bu)

        response = self.staff_client.get(
            f'/api/signatures/reports/unsigned/?document_id={self.document.pk}&business_unit=FILTER-BU'
        )
        self.assertEqual(response.status_code, 200)
        usernames = [u['username'] for u in response.data['results']]
        self.assertEqual(usernames, [bu_user.username])


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class LoginUnsignedCountTests(TestCase):
    """unsigned_count v odpovedi rfid-login (PLAN.md D — cakal na fazu 8)."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_login_returns_unsigned_count(self):
        device = KioskDevice.objects.create(name='Kiosk 1')
        user = make_user()
        make_document(with_file=True)
        signed_doc = make_document(with_file=True)
        Signature.objects.create(user=user, document_version=signed_doc.current_version)

        response = APIClient().post(
            '/api/auth/rfid-login/',
            {'rfid_uid': user.rfid_uid},
            HTTP_X_DEVICE_TOKEN=device.token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['unsigned_count'], 1)
