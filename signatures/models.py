from django.db import models

from core.models import BaseModel


class Signature(BaseModel):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='signatures',
    )
    document_version = models.ForeignKey(
        'documents.DocumentVersion',
        on_delete=models.PROTECT,
        related_name='signatures',
    )
    signed_at = models.DateTimeField(auto_now_add=True)

    rfid_uid_used = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_id = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('user', 'document_version')
        ordering = ['-signed_at']

    def __str__(self):
        return f"{self.user} podpísal {self.document_version}"