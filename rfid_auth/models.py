import secrets

from django.db import models
from django.utils import timezone

from core.models import BaseModel


class KioskDevice(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    location = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RfidSession(BaseModel):
    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='rfid_sessions')
    device = models.ForeignKey(KioskDevice, on_delete=models.SET_NULL, null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'{self.user} @ {self.device}'
