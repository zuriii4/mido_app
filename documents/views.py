import mimetypes

from django.db.models import Count
from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Attachment, DocumentVersion
from documents.serializers import (
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentVersionHistorySerializer,
)
from documents.services import get_unsigned_documents, get_visible_documents


@extend_schema(
    parameters=[
        OpenApiParameter(
            'unsigned', bool, description='true = len este nepodpisane dokumenty'
        ),
        OpenApiParameter(
            'search', str, description='hlada v cisle dokumentu a nazve'
        ),
    ]
)
class DocumentListView(ListAPIView):
    """GET /api/documents/ — viditelne dokumenty; ?unsigned=true len nepodpisane;
    ?search= hlada podla cisla dokumentu / nazvu."""

    serializer_class = DocumentListSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['document_number', 'title']

    def get_queryset(self):
        unsigned = self.request.query_params.get('unsigned', '').lower() in ('true', '1')
        if unsigned:
            return get_unsigned_documents(self.request.user)
        return get_visible_documents(self.request.user)


class DocumentDetailView(RetrieveAPIView):
    """GET /api/documents/{id}/ — detail + aktualna verzia + prilohy."""

    serializer_class = DocumentDetailSerializer

    def get_queryset(self):
        # neviditelny dokument = 404 (nezverejnujeme, ze existuje)
        return get_visible_documents(self.request.user)


@extend_schema(responses=DocumentVersionHistorySerializer(many=True))
class DocumentVersionsView(APIView):
    """GET /api/documents/{id}/versions/ — historia verzii + pocty podpisov."""

    def get(self, request, pk):
        document = get_visible_documents(request.user).filter(pk=pk).first()
        if document is None:
            raise Http404
        versions = (
            document.versions
            .annotate(signature_count=Count('signatures'))
            .order_by('-version_label')
        )
        serializer = DocumentVersionHistorySerializer(versions, many=True)
        return Response(serializer.data)


def _visible_version_or_404(user, version_pk):
    version = (
        DocumentVersion.objects
        .select_related('document')
        .filter(pk=version_pk, document__in=get_visible_documents(user))
        .first()
    )
    if version is None:
        raise Http404
    return version


@extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
class DocumentVersionFileView(APIView):
    """GET /api/documents/versions/{id}/file/ — PDF snapshot verzie.
    404 kym download nie je hotovy alebo dokument nie je viditelny."""

    def get(self, request, pk):
        version = _visible_version_or_404(request.user, pk)
        if not version.file_path:
            raise Http404('Subor este nie je stiahnuty.')
        return FileResponse(
            version.file_path.open('rb'),
            content_type='application/pdf',
            as_attachment=False,
            filename=f'{version.document.title}_v{version.version_label}.pdf',
        )


@extend_schema(responses={(200, '*/*'): OpenApiTypes.BINARY})
class AttachmentFileView(APIView):
    """GET /api/documents/attachments/{id}/file/ — stream prilohy."""

    def get(self, request, pk):
        attachment = (
            Attachment.objects
            .select_related('document_version__document')
            .filter(pk=pk)
            .first()
        )
        if attachment is None or not attachment.file_path:
            raise Http404
        # pristup len cez viditelny dokument
        _visible_version_or_404(request.user, attachment.document_version_id)

        if attachment.converted_to_pdf:
            content_type = 'application/pdf'
        else:
            content_type = mimetypes.guess_type(attachment.file_name)[0] or 'application/octet-stream'
        return FileResponse(
            attachment.file_path.open('rb'),
            content_type=content_type,
            as_attachment=False,
            filename=attachment.file_name,
        )
