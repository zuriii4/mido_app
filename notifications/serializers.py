from rest_framework import serializers

from notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Notification
        fields = ['id', 'document', 'message', 'is_read', 'created_at']
        read_only_fields = fields

class MarkAsReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'is_read', 'created_at', 'document', 'message']
        read_only_fields = fields
