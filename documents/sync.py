import logging
from collections import defaultdict

from django.core.files.base import ContentFile
from django.utils import timezone

from documents.models import Attachment, Document, DocumentVersion
from integrations.sharepoint import get_sharepoint_client
from notifications.services import create_notifications_for_document

logger = logging.getLogger(__name__)


def _as_pdf_filename(file_name):
    base = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
    return f'{base}.pdf'


def _version_key(version_label):
    """Poradie verzii: '-' (prve vydanie) je najnizsie, potom A < B < ... < Z < AA ...
    (dlzka pred abecedou, aby dvojpismenove verzie boli vyssie ako jednopismenove)."""
    return (version_label != '-', len(version_label), version_label)


def sync_documents(client=None, limit=None):
    client = client or get_sharepoint_client()
    run_started_at = timezone.now()
    stats = {
        'seen': 0, 'documents': 0, 'versions_created': 0, 'versions_updated': 0,
        'unchanged': 0, 'skipped_no_number': 0, 'deactivated': 0, 'errors': 0,
    }

    # nazbieraj polozky (potrebujeme ich zoskupit podla cisla dokumentu)
    items = []
    for page in client.iter_document_items():
        for item in page:
            if limit is not None and len(items) >= limit:
                break
            items.append(item)
        if limit is not None and len(items) >= limit:
            break
    stats['seen'] = len(items)

    groups = defaultdict(list)
    for item in items:
        number = item['document_number']
        if not number:
            # polozky bez cisla (napr. stav "Priprava dokumentu...") preskakujeme
            stats['skipped_no_number'] += 1
            continue
        groups[number].append(item)

    seen_numbers = set()
    for number, group in groups.items():
        seen_numbers.add(number)
        try:
            _sync_document_group(client, number, group, run_started_at, stats)
        except Exception:
            stats['errors'] += 1
            logger.exception('Sync dokumentu zlyhal (cislo=%r)', number)

    if limit is None:
        deactivated = (
            Document.objects
            .filter(is_active=True)
            .exclude(document_number__in=seen_numbers)
            .update(is_active=False, last_synced_at=run_started_at)
        )
        stats['deactivated'] = deactivated

    logger.info('sync_documents dokoncene: %s', stats)
    return stats


def _sync_document_group(client, number, group, run_started_at, stats):
    document, _created = Document.objects.get_or_create(
        document_number=number,
        defaults={'title': group[0]['title']},
    )
    stats['documents'] += 1

    # metadata dokumentu berieme z najnovsej (najvyssej) verzie v skupine
    latest = max(group, key=lambda it: _version_key(it['version_label']))
    document.title = latest['title']
    document.ac_dokument_id = latest['ac_dokument_id']
    document.ac_master_id = latest['ac_master_id']
    document.content_type_name = latest['content_type_name']
    document.effective_date = latest['effective_date']
    document.sp_state = latest['sp_state']
    document.note = latest['note']
    document.sp_link = latest['sp_link']
    document.sp_modified_at = latest['sp_modified_at']
    document.full_path = f"acLibPlatne/{latest['file_name']}"
    document.is_active = (latest['sp_state'] == 'Platný')
    document.last_synced_at = run_started_at
    document.save()

    for item in group:
        # chyba jednej verzie nesmie zhodit ostatne verzie ani nastavenie aktualnej
        try:
            _sync_one_version(client, document, item, stats)
        except Exception:
            stats['errors'] += 1
            logger.exception('Sync verzie zlyhal (cislo=%r, verzia=%r, sp_id=%s)',
                             number, item['version_label'], item['sharepoint_id'])

    _set_current_version(document, group)
    created_notifications = create_notifications_for_document(document)
    if created_notifications:
        logger.info('Dokument %r: vytvorene %d notifikacie pre novych podpisujucich',
                    document.document_number, created_notifications)


def _sync_one_version(client, document, item, stats):
    version, created = DocumentVersion.objects.get_or_create(
        sharepoint_id=item['sharepoint_id'],
        defaults={'document': document, 'version_label': item['version_label']},
    )
    etag_changed = created or version.etag != item['etag']

    version.document = document
    version.version_label = item['version_label']
    version.title = item['title']
    version.sp_ui_version = item['sp_ui_version']
    version.effective_date = item['effective_date']
    version.sp_modified_at = item['sp_modified_at']
    version.save()

    if not etag_changed and version.file_path:
        stats['unchanged'] += 1
        return

    # (re)stiahni PDF snapshot tejto verzie
    drive_item = client.get_drive_item_for_list_item(item['sharepoint_id'])
    pdf_bytes = client.download_document_pdf(drive_item['drive_id'], drive_item['drive_item_id'])
    if version.file_path:
        version.file_path.delete(save=False)
    filename = f"{document.id}_{item['sharepoint_id']}_v{version.version_label}.pdf"
    version.file_path.save(filename, ContentFile(pdf_bytes), save=False)
    version.etag = item['etag']  # etag az po uspesnom stiahnuti (idempotencia pri padoch)
    version.save()

    reconcile_attachments(client, document, version)

    stats['versions_created' if created else 'versions_updated'] += 1
    logger.info('Dokument %r: verzia %s %s (%d bajtov, sp verzia %s)',
                document.document_number, version.version_label,
                'vytvorena' if created else 'aktualizovana', len(pdf_bytes), item['sp_ui_version'])


def _set_current_version(document, group):
    """Aktualna verzia = najvyssia verzia z tych, ktore su TERAZ pritomne v Platne.
    Uprednostni verzie so stiahnutym suborom (keby download vyssej verzie zlyhal)."""
    seen_ids = [it['sharepoint_id'] for it in group]
    seen_versions = list(document.versions.filter(sharepoint_id__in=seen_ids))
    with_file = [v for v in seen_versions if v.file_path]
    candidates = with_file or seen_versions
    if not candidates:
        return
    current = max(candidates, key=lambda v: _version_key(v.version_label))
    document.versions.exclude(pk=current.pk).update(is_current=False)
    document.versions.filter(pk=current.pk).update(is_current=True)


def reconcile_attachments(client, document, version):

    if not document.ac_dokument_id:
        return

    remote_attachments = client.list_attachment_folder(document.ac_dokument_id)
    if not remote_attachments:
        return

    previous_version = (
        document.versions
        .exclude(pk=version.pk)
        .order_by('-version_label')
        .first()
    )
    previous_by_sp_id = {}
    if previous_version is not None:
        previous_by_sp_id = {a.sp_item_id: a for a in previous_version.attachments.all() if a.sp_item_id}

    for remote in remote_attachments:
        previous = previous_by_sp_id.get(remote['sp_item_id'])
        if previous is not None and previous.etag == remote['etag'] and previous.file_path:
            with previous.file_path.open('rb') as f:
                content = f.read()
            converted_to_pdf = previous.converted_to_pdf
        else:
            content, converted_to_pdf = client.download_attachment(remote['sp_item_id'], remote['file_name'])

        attachment = Attachment(
            document_version=version,
            file_name=remote['file_name'],
            sp_item_id=remote['sp_item_id'],
            etag=remote['etag'],
            server_relative_url=remote['server_relative_url'],
            file_size=remote['file_size'],
            sp_modified_at=remote['sp_modified_at'],
            converted_to_pdf=converted_to_pdf,
        )
        saved_name = _as_pdf_filename(remote['file_name']) if converted_to_pdf else remote['file_name']
        attachment.file_path.save(saved_name, ContentFile(content), save=True)

    logger.info('Dokument "%s": %d priloh zosynchronizovanych pre verziu %s',
                document.title, len(remote_attachments), version.version_label)


def sweep_attachments(client=None):
    """Periodicky prejde VSETKY aktivne dokumenty a zosynchronizuje ich prilohy,
    nezavisle od toho, ci sa zmenil etag dokumentu - prilohy su v inej kniznici
    (acLibPrilohy) a jej zmeny etag dokumentu vobec nepokryva (viz reconcile_attachments,
    ktora sa vola len ked sa zmeni dokument samotny).

    Na rozdiel od reconcile_attachments() (vytvara nove Attachment riadky pre novu
    verziu) tu aktualizujeme prilohy AKTUALNEJ verzie NA MIESTE - nevznika nova
    DocumentVersion, existujuce podpisy ostavaju platne (rozhodnutie: zmena prilohy
    sama o sebe nevyzaduje nove oboznamenie/podpis).
    """
    client = client or get_sharepoint_client()
    stats = {'documents_checked': 0, 'created': 0, 'updated': 0, 'deleted': 0, 'unchanged': 0, 'errors': 0}

    documents = Document.objects.filter(is_active=True).exclude(ac_dokument_id='')
    for document in documents:
        version = document.current_version
        if version is None or not version.file_path:
            continue
        stats['documents_checked'] += 1
        try:
            _sweep_one_document(client, document, version, stats)
        except Exception:
            stats['errors'] += 1
            logger.exception('Sweep priloh zlyhal (document=%r)', document.title)

    logger.info('sweep_attachments dokoncene: %s', stats)
    return stats


def _sweep_one_document(client, document, version, stats):
    remote_attachments = client.list_attachment_folder(document.ac_dokument_id)
    existing_by_sp_id = {a.sp_item_id: a for a in version.attachments.all() if a.sp_item_id}
    remote_sp_ids = set()

    for remote in remote_attachments:
        remote_sp_ids.add(remote['sp_item_id'])
        existing = existing_by_sp_id.get(remote['sp_item_id'])

        if existing is not None and existing.etag == remote['etag']:
            stats['unchanged'] += 1
            continue

        content, converted_to_pdf = client.download_attachment(remote['sp_item_id'], remote['file_name'])
        saved_name = _as_pdf_filename(remote['file_name']) if converted_to_pdf else remote['file_name']

        if existing is not None:
            existing.file_path.delete(save=False)  # stary subor nenechavame ako sirotu na disku
            existing.file_name = remote['file_name']
            existing.etag = remote['etag']
            existing.server_relative_url = remote['server_relative_url']
            existing.file_size = remote['file_size']
            existing.sp_modified_at = remote['sp_modified_at']
            existing.converted_to_pdf = converted_to_pdf
            existing.file_path.save(saved_name, ContentFile(content), save=True)
            stats['updated'] += 1
        else:
            attachment = Attachment(
                document_version=version,
                file_name=remote['file_name'],
                sp_item_id=remote['sp_item_id'],
                etag=remote['etag'],
                server_relative_url=remote['server_relative_url'],
                file_size=remote['file_size'],
                sp_modified_at=remote['sp_modified_at'],
                converted_to_pdf=converted_to_pdf,
            )
            attachment.file_path.save(saved_name, ContentFile(content), save=True)
            stats['created'] += 1

    removed_ids = set(existing_by_sp_id.keys()) - remote_sp_ids
    for sp_id in removed_ids:
        attachment = existing_by_sp_id[sp_id]
        attachment.file_path.delete(save=False)
        attachment.delete()
        stats['deleted'] += 1
