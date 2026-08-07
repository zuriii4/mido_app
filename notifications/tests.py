from django.test import TestCase

from documents.models import Document, DocumentAssignment, DocumentVersion
from notifications.models import Notification
from notifications.services import (
    create_reminder_notification_for_document,
    get_signed_users_for_document,
    get_unsigned_users_for_document,
)
from signatures.models import Signature
from users.models import BusinessUnit, ProfessionCategory, User


class GetSignedUsersTest(TestCase):
    """Test get_signed_users_for_document."""

    def test_signed_user_in_result(self):
        """Podpisany user je vo vysledku."""
        bu = BusinessUnit.objects.create(code='TBS1')
        user = User.objects.create_user(
            username='signed1', rfid_uid='RF001', external_id='EX001',
            business_unit=bu, is_active=True,
        )
        doc = Document.objects.create(
            document_number='D1', title='Test Doc',
        )
        version = DocumentVersion.objects.create(
            document=doc, version_label='-', is_current=True,
        )
        Signature.objects.create(user=user, document_version=version)

        result = list(get_signed_users_for_document(doc))
        self.assertIn(user, result)

    def test_unsigned_user_not_in_result(self):
        """Nepodpisany user nie je vo vysledku."""
        bu = BusinessUnit.objects.create(code='TBS2')
        user = User.objects.create_user(
            username='unsigned1', rfid_uid='RF002', external_id='EX002',
            business_unit=bu, is_active=True,
        )
        doc = Document.objects.create(
            document_number='D2', title='Test Doc 2',
        )
        DocumentVersion.objects.create(document=doc, version_label='-', is_current=True)

        result = list(get_signed_users_for_document(doc))
        self.assertNotIn(user, result)

    def test_no_current_version_empty(self):
        """Dokument bez verzie vrati empty."""
        doc = Document.objects.create(document_number='D3', title='No Version')
        result = list(get_signed_users_for_document(doc))
        self.assertEqual(len(result), 0)


class CreateReminderNotificationsTest(TestCase):
    """Test create_reminder_notification_for_document."""

    def test_creates_for_user_in_bu(self):
        """Vytvori notifikaciu pre usera v priradenej BU."""
        bu = BusinessUnit.objects.create(code='TBS3')
        user = User.objects.create_user(
            username='remuser1', rfid_uid='RF003', external_id='EX003',
            business_unit=bu, is_active=True,
        )
        doc = Document.objects.create(
            document_number='D4', title='Doc BU',
        )
        version = DocumentVersion.objects.create(document=doc, version_label='-', is_current=True)
        assignment = DocumentAssignment.objects.create(
            document_version=version,
            target_type=DocumentAssignment.TARGET_BUSINESS_UNIT,
        )
        assignment.business_units.add(bu)

        count = create_reminder_notification_for_document(doc)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(Notification.objects.filter(user=user, document=doc).exists())

    def test_idempotent_no_duplicates(self):
        """Druhe spustenie nevytvori duplikaty."""
        bu = BusinessUnit.objects.create(code='TBS4')
        user = User.objects.create_user(
            username='remuser2', rfid_uid='RF004', external_id='EX004',
            business_unit=bu, is_active=True,
        )
        doc = Document.objects.create(
            document_number='D5', title='Doc I',
        )
        version = DocumentVersion.objects.create(document=doc, version_label='-', is_current=True)
        assignment = DocumentAssignment.objects.create(
            document_version=version,
            target_type=DocumentAssignment.TARGET_BUSINESS_UNIT,
        )
        assignment.business_units.add(bu)

        count1 = create_reminder_notification_for_document(doc)
        count2 = create_reminder_notification_for_document(doc)

        self.assertGreater(count1, 0)
        self.assertEqual(count2, 0)
        self.assertEqual(Notification.objects.filter(user=user, document=doc).count(), 1)

    def test_no_version_zero(self):
        """Dokument bez verzie nerobi nic."""
        doc = Document.objects.create(document_number='D6', title='No Ver')
        count = create_reminder_notification_for_document(doc)
        self.assertEqual(count, 0)

    def test_old_version_signed_new_reminder(self):
        """User co podpisal starsiu verziu dostane reminder na novu."""
        bu = BusinessUnit.objects.create(code='TBS5')
        user = User.objects.create_user(
            username='remuser3', rfid_uid='RF005', external_id='EX005',
            business_unit=bu, is_active=True,
        )
        doc = Document.objects.create(
            document_number='D7', title='Doc MultiVer',
        )
        old = DocumentVersion.objects.create(
            document=doc, version_label='-', is_current=False,
        )
        new = DocumentVersion.objects.create(
            document=doc, version_label='A', is_current=True,
        )
        assignment = DocumentAssignment.objects.create(
            document_version=new,
            target_type=DocumentAssignment.TARGET_BUSINESS_UNIT,
        )
        assignment.business_units.add(bu)
        Signature.objects.create(user=user, document_version=old)

        count = create_reminder_notification_for_document(doc)
        self.assertGreater(count, 0)
        self.assertTrue(Notification.objects.filter(user=user, document=doc).exists())
