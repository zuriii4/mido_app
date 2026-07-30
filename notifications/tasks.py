import logging

from celery import shared_task
from documents.models import Document
from notifications.services import create_reminder_notification_for_document

logger = logging.getLogger(__name__)

def get_document_by_number(document_number):
    """
    Returns a Document instance based on the provided document number.
    """
    try:
        return Document.objects.get(document_number=document_number)
    except Document.DoesNotExist:
        logger.error(f'Document with number {document_number} does not exist.')
        return None

def send_reminder_notifications_for_document(document_id):
    """
    Celery task to send reminder notifications for a specific document.
    """

    try:
        document = Document.objects.get(id=document_id)
        num_notifications = create_reminder_notification_for_document(document)
        logger.info(f'Sent {num_notifications} reminder notifications for document ID {document_id}.')
        return num_notifications
    except Document.DoesNotExist:
        logger.error(f'Document with ID {document_id} does not exist.')
        return 0


@shared_task(name='send_reminders')
def send_reminders_task():
    """
    Celery task to send reminders notifications for all documents
    """
    active_documents = Document.objects.filter(is_active=True, versions__is_current=True).distinct()
    count = 0
    for document in active_documents:
        count += send_reminder_notifications_for_document(document.id)

    logger.info(f'Sent reminder notifications for {count} documents.')
    return count