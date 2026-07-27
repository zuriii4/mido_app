from rest_framework import serializers

from users.serializers import UserSerializer


class RfidLoginSerializer(serializers.Serializer):
    rfid_uid = serializers.CharField(max_length=60)


class RfidLoginResponseSerializer(serializers.Serializer):
    """Len pre OpenAPI schemu — popisuje odpoved rfid-login."""
    token = serializers.CharField()
    expires_at = serializers.DateTimeField()
    user = UserSerializer()
    unsigned_count = serializers.IntegerField()
