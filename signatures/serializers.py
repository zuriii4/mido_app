from rest_framework import serializers

from signatures.models import Signature


class SignRequestSerializer(serializers.Serializer):
    document_version_id = serializers.UUIDField()
    rfid_uid = serializers.CharField(max_length=60)  # re-tap karty na kiosku


class SignatureSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source='document_version.document.title', read_only=True)
    document_id = serializers.UUIDField(source='document_version.document_id', read_only=True)
    version_label = serializers.CharField(source='document_version.version_label', read_only=True)

    class Meta:
        model = Signature
        fields = [
            'id', 'document_id', 'document_title', 'document_version',
            'version_label', 'signed_at', 'device_id',
        ]
        read_only_fields = fields


class SignatureReportSerializer(serializers.ModelSerializer):
    """Staff report: kto podpisal ktoru verziu."""
    user_id = serializers.UUIDField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    version_label = serializers.CharField(source='document_version.version_label', read_only=True)

    class Meta:
        model = Signature
        fields = [
            'id', 'user_id', 'username', 'full_name', 'document_version',
            'version_label', 'signed_at', 'rfid_uid_used', 'device_id', 'ip_address',
        ]
        read_only_fields = fields
