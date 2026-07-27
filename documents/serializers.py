from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.reverse import reverse

from documents.models import Attachment, Document, DocumentVersion


class AttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ['id', 'file_name', 'file_size', 'converted_to_pdf', 'sp_modified_at', 'file_url']

    @extend_schema_field(OpenApiTypes.URI)
    def get_file_url(self, obj):
        return reverse('attachment-file', args=[obj.pk], request=self.context.get('request'))


class DocumentVersionSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            'id', 'version_label', 'title', 'sp_ui_version', 'is_current',
            'effective_date', 'published_at', 'file_url', 'attachments',
        ]

    @extend_schema_field(OpenApiTypes.URI)
    def get_file_url(self, obj):
        if not obj.file_path:
            return None  # download este nedobehol
        return reverse('document-version-file', args=[obj.pk], request=self.context.get('request'))


class DocumentVersionHistorySerializer(serializers.ModelSerializer):
    """Polozka historie verzii (bez priloh, s poctom podpisov)."""
    signature_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DocumentVersion
        fields = [
            'id', 'version_label', 'title', 'sp_ui_version', 'is_current',
            'effective_date', 'published_at', 'signature_count',
        ]


class DocumentListSerializer(serializers.ModelSerializer):
    current_version_id = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'document_number', 'title', 'content_type_name', 'effective_date',
            'sp_state', 'note', 'current_version_id',
        ]

    @extend_schema_field(OpenApiTypes.UUID)
    def get_current_version_id(self, obj):
        version = obj.current_version
        return version.pk if version else None


class DocumentDetailSerializer(serializers.ModelSerializer):
    current_version = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'document_number', 'title', 'content_type_name', 'effective_date',
            'sp_state', 'note', 'sp_link', 'current_version',
        ]

    @extend_schema_field(DocumentVersionSerializer)
    def get_current_version(self, obj):
        version = obj.current_version
        if version is None:
            return None
        return DocumentVersionSerializer(version, context=self.context).data
