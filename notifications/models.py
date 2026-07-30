from django.db import models

from core.models import BaseModel


class Notification(BaseModel):
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    document = models.ForeignKey(
        'documents.Document',
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    message = models.CharField(max_length=250)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.document.title} - {self.message[:20]}..."
