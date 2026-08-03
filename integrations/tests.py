from unittest.mock import MagicMock

from django.test import SimpleTestCase

from integrations.sharepoint import SharePointSyncClient


def _client():
    client = SharePointSyncClient.__new__(SharePointSyncClient)
    client.graph = MagicMock()
    client.graph.get_bytes.return_value = b'%PDF-1.4 bytes'
    return client


class DownloadDocumentPdfTests(SimpleTestCase):
    """Regresia: dokument 80000001 (sp_id=532) je v SharePointe uz PDF a
    Graph konverzia pdf->pdf zlyhala s 406 Not Acceptable."""

    def test_pdf_source_downloads_original_without_conversion(self):
        client = _client()
        result = client.download_document_pdf('drive-1', 'item-1', 'Smernica.pdf')
        self.assertEqual(result, b'%PDF-1.4 bytes')
        client.graph.get_bytes.assert_called_once_with('drives/drive-1/items/item-1/content')

    def test_pdf_source_uppercase_extension(self):
        client = _client()
        client.download_document_pdf('drive-1', 'item-1', 'Smernica.PDF')
        client.graph.get_bytes.assert_called_once_with('drives/drive-1/items/item-1/content')

    def test_docx_source_requests_pdf_conversion(self):
        client = _client()
        client.download_document_pdf('drive-1', 'item-1', 'Smernica.docx')
        client.graph.get_bytes.assert_called_once_with(
            'drives/drive-1/items/item-1/content', params={'format': 'pdf'})

    def test_no_file_name_keeps_conversion(self):
        client = _client()
        client.download_document_pdf('drive-1', 'item-1')
        client.graph.get_bytes.assert_called_once_with(
            'drives/drive-1/items/item-1/content', params={'format': 'pdf'})
