import logging
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.utils.dateparse import parse_datetime

from integrations.graph_client import GraphClient

logger = logging.getLogger(__name__)

PAGE_SIZE = 200


SP_SITE_TZ = ZoneInfo('Europe/Bratislava')


def _int_or_none(value):
    if value in (None, ''):
        return None
    return int(float(value))


def _date_or_none(value):
    dt = parse_datetime(value) if value else None
    if dt is None:
        return None
    return dt.astimezone(SP_SITE_TZ).date()


def parse_document_item(raw_item: dict) -> dict:
    """Rozparsuje jednu polozku z GET (acLibPlatne)."""
    fields = raw_item.get('fields', raw_item)
    return {
        'sharepoint_id': int(raw_item['id']),
        # Cislo dokumentu (identita naprie verziami) a Verzia dokumentu (- / A / B / ...)
        'document_number': (fields.get('acColCisloDokumentu') or '').strip(),
        'version_label': (fields.get('acColVerzia') or '-').strip() or '-',
        'title': fields.get('Title', ''),
        'file_name': fields.get('FileLeafRef', ''),
        'ac_dokument_id': str(_int_or_none(fields.get('acColDokumentID')) or ''),
        'ac_master_id': str(_int_or_none(fields.get('acColMasterID')) or ''),
        'etag': raw_item.get('eTag', ''),
        'content_type_name': fields.get('ContentType', ''),
        'effective_date': _date_or_none(fields.get('acColDatUcinnosti')),
        'sp_state': fields.get('acColStavDokumentu', ''),
        'note': fields.get('acColPoznamkaMulti', '') or '',
        'sp_link': raw_item.get('webUrl', ''),
        'sp_modified_at': parse_datetime(fields.get('Modified')) if fields.get('Modified') else None,
        'sp_ui_version': fields.get('_UIVersionString', ''),
    }


def parse_attachment_item(drive_item: dict) -> dict:
    """Rozparsuje jednu polozku z GET (acLibPrilohy)."""
    file_info = drive_item.get('file', {})
    return {
        'sp_item_id': drive_item.get('id', ''),
        'file_name': drive_item.get('name', ''),
        'etag': drive_item.get('eTag', ''),
        'server_relative_url': drive_item.get('parentReference', {}).get('path', '') + '/' + drive_item.get('name', ''),
        'file_size': drive_item.get('size'),
        'sp_modified_at': parse_datetime(drive_item.get('lastModifiedDateTime')) if drive_item.get('lastModifiedDateTime') else None,
        'mime_type': file_info.get('mimeType', ''),
    }


class SharePointSyncClient:
    """sync dokumentov a priloh."""

    def __init__(self, graph_client: GraphClient | None = None):
        self.graph = graph_client or GraphClient()
        self.site_id = settings.SP_SITE_ID
        self.list_platne_id = settings.SP_LIST_PLATNE_ID
        self.list_prilohy_id = settings.SP_LIST_PRILOHY_ID
        self.prilohy_drive_id = settings.SP_PRILOHY_DRIVE_ID

    def iter_document_items(self, page_size: int = PAGE_SIZE):
        """vracia stranky (list) rozparsovanych polozok z acLibPlatne."""
        url = f'sites/{self.site_id}/lists/{self.list_platne_id}/items'
        params = {'$expand': 'fields', '$top': page_size}
        for page_num, raw_page in enumerate(self.graph.get_json_paged(url, params=params), start=1):
            logger.info('acLibPlatne: stranka %d, %d poloziek', page_num, len(raw_page))
            yield [parse_document_item(item) for item in raw_page]

    def get_drive_item_for_list_item(self, sharepoint_id: int) -> dict:
        """Vrati {'drive_id', 'drive_item_id', 'size'} pre polozku - potrebne az ked sa
        dokument zmenil (etag)"""
        url = f'sites/{self.site_id}/lists/{self.list_platne_id}/items/{sharepoint_id}/driveItem'
        data = self.graph.get_json(url)
        return {
            'drive_id': data.get('parentReference', {}).get('driveId', ''),
            'drive_item_id': data.get('id', ''),
            'size': data.get('size'),
        }

    def download_document_pdf(self, drive_id: str, drive_item_id: str, file_name: str = '') -> bytes:
        """Stiahne obsah suboru konvertovany na PDF (docx -> pdf on-the-fly cez Graph).
        Uz existujuce PDF sa nekonvertuje znova - konverziu pdf->pdf Graph
        odmietne (406 Not Acceptable), tak sa stiahne original."""
        url = f'drives/{drive_id}/items/{drive_item_id}/content'
        if file_name.lower().endswith('.pdf'):
            return self.graph.get_bytes(url)
        return self.graph.get_bytes(url, params={'format': 'pdf'})

    def list_attachment_folder(self, ac_dokument_id: str) -> list[dict]:
        """Vrati zoznam priloh v priecinku acLibPrilohy/<ac_dokument_id>.
        Ak priecinok neexistuje/je prazdny, Graph vracia 200 s prazdnym 'value'."""
        if not ac_dokument_id:
            return []
        url = f'drives/{self.prilohy_drive_id}/root:/{ac_dokument_id}:/children'
        data = self.graph.get_json(url, params={'$top': 200})
        items = data.get('value', [])
        return [parse_attachment_item(it) for it in items if 'file' in it]

    def download_attachment(self, sp_item_id: str, file_name: str = '') -> tuple[bytes, bool]:
        """Stiahne prilohu. Skusi PDF snapshot ('?format=pdf'). Ak SharePoint konverziu pre
        dany format nepodporuje (napr. .json, .zip - vracia 4xx), padne na
        stiahnutie originalu. Uz existujuce PDF sa nekonvertuju znova."""
        url = f'drives/{self.prilohy_drive_id}/items/{sp_item_id}/content'

        if file_name.lower().endswith('.pdf'):
            return self.graph.get_bytes(url), True

        try:
            return self.graph.get_bytes(url, params={'format': 'pdf'}), True
        except requests.HTTPError as exc:
            logger.info('PDF konverzia prilohy %r nepodporovana (%s), stahujem original', file_name, exc)
            return self.graph.get_bytes(url), False


def get_sharepoint_client() -> SharePointSyncClient:
    return SharePointSyncClient()
