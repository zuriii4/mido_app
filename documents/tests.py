import shutil
import tempfile

from django.test import TestCase, override_settings
from django.utils import timezone

from documents.models import Attachment, Document, DocumentVersion
from documents.sync import sync_documents, sweep_attachments

MEDIA_ROOT = tempfile.mkdtemp(prefix='mido_documents_tests_')


def doc_item(sharepoint_id, document_number=None, version_label='-', title='Smernica BOZP',
             etag='etag-1', ac_dokument_id='DOC-1', sp_state='Platný', **overrides):
    # default: kazdy sharepoint_id = ine cislo dokumentu (samostatny dokument);
    # rovnaku verziu toho isteho dokumentu vymodelujes rovnakym document_number.
    if document_number is None:
        document_number = f'OS-90-{sharepoint_id:02d}/21'
    item = {
        'sharepoint_id': sharepoint_id,
        'document_number': document_number,
        'version_label': version_label,
        'title': title,
        'file_name': f'{title}.docx',
        'ac_dokument_id': ac_dokument_id,
        'ac_master_id': 'MASTER-1',
        'etag': etag,
        'content_type_name': 'Dokument',
        'effective_date': None,
        'sp_state': sp_state,
        'note': '',
        'sp_link': 'https://sharepoint.example/doc',
        'sp_modified_at': timezone.now(),
        'sp_ui_version': '1.0',
    }
    item.update(overrides)
    return item


def attachment_item(sp_item_id, file_name='priloha.pdf', etag='att-etag-1'):
    return {
        'sp_item_id': sp_item_id,
        'file_name': file_name,
        'etag': etag,
        'server_relative_url': f'/acLibPrilohy/{file_name}',
        'file_size': 123,
        'sp_modified_at': timezone.now(),
    }


class FakeSharePointClient:
    """Fake SharePointSyncClient - duck-types same interface as sync.py potrebuje,
    ale bez volania Microsoft Graph."""

    def __init__(self, document_pages=None, attachments_by_dokument_id=None):
        self.document_pages = document_pages or []
        self.attachments_by_dokument_id = attachments_by_dokument_id or {}
        self.downloaded_documents = []
        self.downloaded_attachments = []

    def iter_document_items(self, page_size=200):
        for page in self.document_pages:
            yield page

    def get_drive_item_for_list_item(self, sharepoint_id):
        return {'drive_id': 'drive-1', 'drive_item_id': f'item-{sharepoint_id}', 'size': 100}

    def download_document_pdf(self, drive_id, drive_item_id):
        self.downloaded_documents.append(drive_item_id)
        return b'%PDF-1.4 fake document content'

    def list_attachment_folder(self, ac_dokument_id):
        return self.attachments_by_dokument_id.get(ac_dokument_id, [])

    def download_attachment(self, sp_item_id, file_name=''):
        self.downloaded_attachments.append(sp_item_id)
        return b'fake attachment bytes', True


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SyncDocumentsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def test_creates_new_document_with_first_version(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1)]])

        stats = sync_documents(client=client)

        self.assertEqual(stats['documents'], 1)
        self.assertEqual(stats['versions_created'], 1)
        self.assertEqual(stats['seen'], 1)
        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertEqual(document.title, 'Smernica BOZP')
        self.assertTrue(document.is_active)
        version = document.current_version
        self.assertIsNotNone(version)
        self.assertEqual(version.version_label, '-')
        self.assertEqual(version.sharepoint_id, 1)
        self.assertEqual(version.etag, 'etag-1')
        self.assertTrue(version.is_current)
        self.assertTrue(version.file_path)

    def test_unchanged_etag_skips_redownload(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1, etag='etag-1')]])
        sync_documents(client=client)

        client2 = FakeSharePointClient(document_pages=[[doc_item(1, etag='etag-1')]])
        stats = sync_documents(client=client2)

        self.assertEqual(stats['unchanged'], 1)
        self.assertEqual(stats['versions_created'], 0)
        self.assertEqual(client2.downloaded_documents, [])
        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertEqual(document.versions.count(), 1)

    def test_changed_etag_redownloads_same_version(self):
        """Rovnaka polozka (sharepoint_id) so zmenenym etagom = re-download tej ISTEJ
        verzie, NIE nova verzia (nova verzia = nova list-item polozka s vyssim pismenom)."""
        client = FakeSharePointClient(document_pages=[[doc_item(1, etag='etag-1')]])
        sync_documents(client=client)

        client2 = FakeSharePointClient(document_pages=[[doc_item(1, etag='etag-2')]])
        stats = sync_documents(client=client2)

        self.assertEqual(stats['versions_updated'], 1)
        self.assertEqual(stats['versions_created'], 0)
        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertEqual(document.versions.count(), 1)
        self.assertEqual(document.current_version.etag, 'etag-2')

    def test_new_version_letter_same_number_adds_version_and_retires_old(self):
        """Nova verzia dokumentu = nova polozka s rovnakym cislom a vyssou verziou (A)."""
        num = 'OS-90-01/21'
        client = FakeSharePointClient(document_pages=[[doc_item(1, document_number=num, version_label='-')]])
        sync_documents(client=client)

        client2 = FakeSharePointClient(document_pages=[[
            doc_item(1, document_number=num, version_label='-', etag='etag-1'),
            doc_item(2, document_number=num, version_label='A', title='Smernica BOZP v2'),
        ]])
        stats = sync_documents(client=client2)

        self.assertEqual(stats['documents'], 1)
        self.assertEqual(stats['versions_created'], 1)  # len 'A' je nova
        document = Document.objects.get(document_number=num)
        self.assertEqual(document.versions.count(), 2)
        current = document.current_version
        self.assertEqual(current.version_label, 'A')
        self.assertEqual(current.sharepoint_id, 2)
        self.assertEqual(document.title, 'Smernica BOZP v2')  # metadata z najnovsej verzie
        old = document.versions.get(version_label='-')
        self.assertFalse(old.is_current)

    def test_superseding_version_becomes_current_even_if_old_left_platne(self):
        """Ked '-' zmizne z Platne a ostane len 'A', aktualna je 'A', '-' ostava historia."""
        num = 'OS-90-01/21'
        sync_documents(client=FakeSharePointClient(
            document_pages=[[doc_item(1, document_number=num, version_label='-')]]))
        sync_documents(client=FakeSharePointClient(
            document_pages=[[doc_item(2, document_number=num, version_label='A')]]), limit=10)

        document = Document.objects.get(document_number=num)
        self.assertEqual(document.versions.count(), 2)
        self.assertEqual(document.current_version.version_label, 'A')
        self.assertFalse(document.versions.get(version_label='-').is_current)

    def test_item_without_document_number_is_skipped(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1, document_number='')]])
        stats = sync_documents(client=client)

        self.assertEqual(stats['skipped_no_number'], 1)
        self.assertEqual(stats['documents'], 0)
        self.assertEqual(Document.objects.count(), 0)

    def test_document_deactivated_when_missing_from_sharepoint(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1)]])
        sync_documents(client=client)

        # dalsi beh uz vidi len prazdny zoznam - dokument zmizol zo SharePointu
        client2 = FakeSharePointClient(document_pages=[[]])
        stats = sync_documents(client=client2)

        self.assertEqual(stats['deactivated'], 1)
        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertFalse(document.is_active)

    def test_limit_skips_deactivation_pass(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1)]])
        sync_documents(client=client)

        client2 = FakeSharePointClient(document_pages=[[]])
        stats = sync_documents(client=client2, limit=5)

        self.assertEqual(stats['deactivated'], 0)
        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertTrue(document.is_active)

    def test_sp_state_other_than_platny_marks_inactive(self):
        client = FakeSharePointClient(document_pages=[[doc_item(1, sp_state='Neplatný')]])
        sync_documents(client=client)

        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertFalse(document.is_active)

    def test_error_on_one_item_does_not_abort_others(self):
        bad_item = doc_item(1)
        del bad_item['title']  # sposobi KeyError vnutri _sync_document_group (za try/except)
        good_item = doc_item(2)  # ine cislo dokumentu = ina skupina
        client = FakeSharePointClient(document_pages=[[bad_item, good_item]])

        stats = sync_documents(client=client)

        self.assertEqual(stats['errors'], 1)
        self.assertEqual(stats['versions_created'], 1)
        self.assertTrue(Document.objects.filter(document_number='OS-90-02/21').exists())

    def test_attachments_are_reconciled_for_new_version(self):
        client = FakeSharePointClient(
            document_pages=[[doc_item(1, ac_dokument_id='DOC-1')]],
            attachments_by_dokument_id={'DOC-1': [attachment_item('att-1'), attachment_item('att-2')]},
        )

        sync_documents(client=client)

        document = Document.objects.get(document_number='OS-90-01/21')
        version = document.current_version
        self.assertEqual(version.attachments.count(), 2)
        self.assertCountEqual(
            version.attachments.values_list('sp_item_id', flat=True), ['att-1', 'att-2']
        )

    def test_no_ac_dokument_id_skips_attachment_reconciliation(self):
        client = FakeSharePointClient(
            document_pages=[[doc_item(1, ac_dokument_id='')]],
            attachments_by_dokument_id={'DOC-1': [attachment_item('att-1')]},
        )

        sync_documents(client=client)

        document = Document.objects.get(document_number='OS-90-01/21')
        self.assertEqual(document.current_version.attachments.count(), 0)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SweepAttachmentsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def _sync_one(self, ac_dokument_id='DOC-1', attachments=None):
        client = FakeSharePointClient(
            document_pages=[[doc_item(1, ac_dokument_id=ac_dokument_id)]],
            attachments_by_dokument_id={ac_dokument_id: attachments or []},
        )
        sync_documents(client=client)
        return Document.objects.get(document_number='OS-90-01/21')

    def test_skips_documents_without_current_version(self):
        # dokument bez ac_dokument_id nema po synchronizacii ziadne prilohy,
        # ale current_version stale existuje - test skipovania rieši prazdny queryset nizsie
        Document.objects.all().delete()

        client = FakeSharePointClient()
        stats = sweep_attachments(client=client)

        self.assertEqual(stats['documents_checked'], 0)

    def test_creates_new_attachment_found_on_sweep(self):
        document = self._sync_one(attachments=[])
        version = document.current_version

        sweep_client = FakeSharePointClient(
            attachments_by_dokument_id={'DOC-1': [attachment_item('att-1')]}
        )
        stats = sweep_attachments(client=sweep_client)

        self.assertEqual(stats['created'], 1)
        version.refresh_from_db()
        self.assertEqual(version.attachments.count(), 1)

    def test_unchanged_attachment_is_not_redownloaded(self):
        document = self._sync_one(attachments=[attachment_item('att-1', etag='same-etag')])

        sweep_client = FakeSharePointClient(
            attachments_by_dokument_id={'DOC-1': [attachment_item('att-1', etag='same-etag')]}
        )
        stats = sweep_attachments(client=sweep_client)

        self.assertEqual(stats['unchanged'], 1)
        self.assertEqual(stats['updated'], 0)
        self.assertEqual(sweep_client.downloaded_attachments, [])

    def test_changed_etag_updates_attachment_in_place(self):
        document = self._sync_one(attachments=[attachment_item('att-1', etag='old-etag')])
        version = document.current_version
        original_attachment_pk = version.attachments.get().pk

        sweep_client = FakeSharePointClient(
            attachments_by_dokument_id={'DOC-1': [attachment_item('att-1', etag='new-etag')]}
        )
        stats = sweep_attachments(client=sweep_client)

        self.assertEqual(stats['updated'], 1)
        version.refresh_from_db()
        self.assertEqual(version.attachments.count(), 1)
        updated = version.attachments.get()
        self.assertEqual(updated.pk, original_attachment_pk)
        self.assertEqual(updated.etag, 'new-etag')

    def test_removed_remote_attachment_is_deleted(self):
        document = self._sync_one(attachments=[attachment_item('att-1')])
        version = document.current_version
        self.assertEqual(version.attachments.count(), 1)

        sweep_client = FakeSharePointClient(attachments_by_dokument_id={'DOC-1': []})
        stats = sweep_attachments(client=sweep_client)

        self.assertEqual(stats['deleted'], 1)
        version.refresh_from_db()
        self.assertEqual(version.attachments.count(), 0)

    def test_error_on_one_document_does_not_abort_sweep(self):
        doc1 = self._sync_one(attachments=[attachment_item('att-1')])

        client2 = FakeSharePointClient(
            document_pages=[[doc_item(2, ac_dokument_id='DOC-2')]],
            attachments_by_dokument_id={'DOC-2': [attachment_item('att-2')]},
        )
        # limit= preskoci deaktivacny prechod - inak by tento beh (vidi len dokument 2)
        # deaktivoval dokument 1, ktory by potom sweep_attachments uz vobec nevidel
        sync_documents(client=client2, limit=10)

        class ExplodingClient(FakeSharePointClient):
            def list_attachment_folder(self, ac_dokument_id):
                if ac_dokument_id == 'DOC-1':
                    raise RuntimeError('boom')
                return super().list_attachment_folder(ac_dokument_id)

        sweep_client = ExplodingClient(
            attachments_by_dokument_id={'DOC-2': [attachment_item('att-2', etag='att-etag-2-new')]}
        )
        stats = sweep_attachments(client=sweep_client)

        self.assertEqual(stats['errors'], 1)
        self.assertEqual(stats['updated'], 1)


class DocumentModelTests(TestCase):
    def test_current_version_returns_none_without_versions(self):
        document = Document.objects.create(title='Bez verzie', document_number='BV-1')
        self.assertIsNone(document.current_version)

    def test_str_includes_number_and_title(self):
        document = Document.objects.create(title='Smernica X', document_number='SX-1')
        self.assertEqual(str(document), 'SX-1 · Smernica X')


# ---------------------------------------------------------------------------
# Viditelnost (documents/services.py) a API
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

from rest_framework.test import APIClient  # noqa: E402

from core.testutils import auth_client, make_document, make_user  # noqa: E402
from documents.models import DocumentVisibilityRule  # noqa: E402
from documents.services import (  # noqa: E402
    get_required_users,
    get_unsigned_documents,
    get_visible_documents,
)
from signatures.models import Signature  # noqa: E402
from users.models import BusinessUnit, ProfessionCategory  # noqa: E402


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class VisibilityServiceTests(TestCase):
    def setUp(self):
        self.bu1 = BusinessUnit.objects.create(code='BU1')
        self.bu2 = BusinessUnit.objects.create(code='BU2')
        self.pc1 = ProfessionCategory.objects.create(name='Zvarac')
        self.pc2 = ProfessionCategory.objects.create(name='Uctovnik')
        self.user = make_user(business_unit=self.bu1, profession_code=self.pc1)

    def visible_pks(self, user=None):
        return set(get_visible_documents(user or self.user).values_list('pk', flat=True))

    def test_document_without_restrictions_is_visible(self):
        doc = make_document(with_file=False)
        self.assertIn(doc.pk, self.visible_pks())

    def test_inactive_document_is_never_visible(self):
        doc = make_document(with_file=False, is_active=False)
        self.assertNotIn(doc.pk, self.visible_pks())

    def test_required_bu_blocks_other_bu(self):
        doc = make_document(with_file=False, required_bu=self.bu2)
        self.assertNotIn(doc.pk, self.visible_pks())

    def test_required_bu_allows_matching_bu(self):
        doc = make_document(with_file=False, required_bu=self.bu1)
        self.assertIn(doc.pk, self.visible_pks())

    def test_required_bu_blocks_user_without_bu(self):
        loner = make_user(business_unit=None)
        doc = make_document(with_file=False, required_bu=self.bu1)
        self.assertNotIn(doc.pk, self.visible_pks(loner))

    def test_required_pc_gate(self):
        doc_ok = make_document(with_file=False, required_pc=self.pc1)
        doc_blocked = make_document(with_file=False, required_pc=self.pc2)
        self.assertIn(doc_ok.pk, self.visible_pks())
        self.assertNotIn(doc_blocked.pk, self.visible_pks())

    def test_inclusion_bu_rule_must_match(self):
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_BUSINESS_UNIT,
            business_unit=self.bu2,
        )
        self.assertNotIn(doc.pk, self.visible_pks())

        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_BUSINESS_UNIT,
            business_unit=self.bu1,
        )
        self.assertIn(doc.pk, self.visible_pks())

    def test_inclusion_all_matches_everyone(self):
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc, rule_type=DocumentVisibilityRule.RULE_ALL
        )
        self.assertIn(doc.pk, self.visible_pks())
        self.assertIn(doc.pk, self.visible_pks(make_user()))

    def test_user_explicit_rule(self):
        other = make_user()
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc, rule_type=DocumentVisibilityRule.RULE_USER_EXPLICIT, user=other
        )
        self.assertNotIn(doc.pk, self.visible_pks())
        self.assertIn(doc.pk, self.visible_pks(other))

    def test_both_rule_requires_both(self):
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_BOTH,
            business_unit=self.bu1,
            profession_category=self.pc2,  # pc nesedi
        )
        self.assertNotIn(doc.pk, self.visible_pks())

        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_BOTH,
            business_unit=self.bu1,
            profession_category=self.pc1,
        )
        self.assertIn(doc.pk, self.visible_pks())

    def test_exclusion_rule_removes_document(self):
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc, rule_type=DocumentVisibilityRule.RULE_ALL
        )
        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_USER_EXPLICIT,
            user=self.user,
            is_exclusion=True,
        )
        self.assertNotIn(doc.pk, self.visible_pks())
        self.assertIn(doc.pk, self.visible_pks(make_user()))

    def test_rule_outside_time_window_is_ignored(self):
        now = timezone.now()
        doc = make_document(with_file=False)
        # exspirovana inclusion BU2 - ignoruje sa, dokument ostava viditelny vsetkym
        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_BUSINESS_UNIT,
            business_unit=self.bu2,
            valid_to=now - timedelta(days=1),
        )
        self.assertIn(doc.pk, self.visible_pks())

        # buduca exclusion sa tiez ignoruje
        DocumentVisibilityRule.objects.create(
            document=doc,
            rule_type=DocumentVisibilityRule.RULE_ALL,
            is_exclusion=True,
            valid_from=now + timedelta(days=1),
        )
        self.assertIn(doc.pk, self.visible_pks())

    def test_get_required_users_inverse(self):
        other_bu_user = make_user(business_unit=self.bu2)
        doc = make_document(with_file=False, required_bu=self.bu1)

        required = set(get_required_users(doc).values_list('pk', flat=True))
        self.assertIn(self.user.pk, required)
        self.assertNotIn(other_bu_user.pk, required)

    def test_get_required_users_exclusion_all_means_nobody(self):
        doc = make_document(with_file=False)
        DocumentVisibilityRule.objects.create(
            document=doc, rule_type=DocumentVisibilityRule.RULE_ALL, is_exclusion=True
        )
        self.assertEqual(get_required_users(doc).count(), 0)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UnsignedDocumentsTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def unsigned_pks(self):
        return set(get_unsigned_documents(self.user).values_list('pk', flat=True))

    def test_document_with_file_is_unsigned(self):
        doc = make_document(with_file=True)
        self.assertIn(doc.pk, self.unsigned_pks())

    def test_document_without_downloaded_file_is_excluded(self):
        doc = make_document(with_file=False)
        self.assertNotIn(doc.pk, self.unsigned_pks())

    def test_signed_current_version_is_excluded(self):
        doc = make_document(with_file=True)
        Signature.objects.create(user=self.user, document_version=doc.current_version)
        self.assertNotIn(doc.pk, self.unsigned_pks())

    def test_signature_on_old_version_does_not_count(self):
        doc = make_document(with_file=True)
        old_version = doc.current_version
        Signature.objects.create(user=self.user, document_version=old_version)

        # nova verzia -> stary podpis uz nestaci
        DocumentVersion.objects.filter(pk=old_version.pk).update(is_current=False)
        from django.core.files.base import ContentFile
        new_version = DocumentVersion.objects.create(
            document=doc, version_label='A', is_current=True
        )
        new_version.file_path.save('vA.pdf', ContentFile(b'%PDF-1.4 v2'), save=True)

        self.assertIn(doc.pk, self.unsigned_pks())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class DocumentApiTests(TestCase):
    def setUp(self):
        self.bu1 = BusinessUnit.objects.create(code='BU1')
        self.bu2 = BusinessUnit.objects.create(code='BU2')
        self.user = make_user(business_unit=self.bu1)
        self.client = auth_client(self.user)
        self.visible_doc = make_document(title='Viditelny', with_file=True)
        self.hidden_doc = make_document(title='Skryty', with_file=True, required_bu=self.bu2)

    def test_list_requires_auth(self):
        response = APIClient().get('/api/documents/')
        self.assertIn(response.status_code, (401, 403))

    def test_list_returns_only_visible(self):
        response = self.client.get('/api/documents/')
        self.assertEqual(response.status_code, 200)
        titles = [d['title'] for d in response.data['results']]
        self.assertIn('Viditelny', titles)
        self.assertNotIn('Skryty', titles)

    def test_unsigned_filter_excludes_signed(self):
        Signature.objects.create(user=self.user, document_version=self.visible_doc.current_version)
        response = self.client.get('/api/documents/?unsigned=true')
        self.assertEqual(response.status_code, 200)
        titles = [d['title'] for d in response.data['results']]
        self.assertNotIn('Viditelny', titles)

    def test_detail_returns_current_version_with_file_url(self):
        response = self.client.get(f'/api/documents/{self.visible_doc.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Viditelny')
        self.assertIsNotNone(response.data['current_version'])
        self.assertIsNotNone(response.data['current_version']['file_url'])

    def test_detail_of_invisible_document_is_404(self):
        response = self.client.get(f'/api/documents/{self.hidden_doc.pk}/')
        self.assertEqual(response.status_code, 404)

    def test_versions_history(self):
        response = self.client.get(f'/api/documents/{self.visible_doc.pk}/versions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['version_label'], '-')
        self.assertEqual(response.data[0]['signature_count'], 0)

    def test_version_file_streaming(self):
        version = self.visible_doc.current_version
        response = self.client.get(f'/api/documents/versions/{version.pk}/file/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))

    def test_version_file_404_when_not_downloaded(self):
        doc = make_document(with_file=False)
        response = self.client.get(f'/api/documents/versions/{doc.current_version.pk}/file/')
        self.assertEqual(response.status_code, 404)

    def test_version_file_404_for_invisible_document(self):
        version = self.hidden_doc.current_version
        response = self.client.get(f'/api/documents/versions/{version.pk}/file/')
        self.assertEqual(response.status_code, 404)

    def test_attachment_file_streaming(self):
        from django.core.files.base import ContentFile
        attachment = Attachment(
            document_version=self.visible_doc.current_version,
            file_name='priloha.pdf',
            converted_to_pdf=True,
        )
        attachment.file_path.save('priloha.pdf', ContentFile(b'%PDF-1.4 att'), save=True)

        response = self.client.get(f'/api/documents/attachments/{attachment.pk}/file/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/pdf')

    def test_attachment_file_404_for_invisible_document(self):
        from django.core.files.base import ContentFile
        attachment = Attachment(
            document_version=self.hidden_doc.current_version,
            file_name='priloha.pdf',
            converted_to_pdf=True,
        )
        attachment.file_path.save('priloha.pdf', ContentFile(b'%PDF-1.4 att'), save=True)

        response = self.client.get(f'/api/documents/attachments/{attachment.pk}/file/')
        self.assertEqual(response.status_code, 404)
