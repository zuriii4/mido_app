import logging

from celery import shared_task

from documents.sync import sync_documents, sweep_attachments

logger = logging.getLogger(__name__)


@shared_task(name='documents.sync_documents')
def sync_documents_task():
    stats = sync_documents()
    logger.info('documents.sync_documents task hotovy: %s', stats)
    return stats


@shared_task(name='documents.sweep_attachments')
def sweep_attachments_task():
    stats = sweep_attachments()
    logger.info('documents.sweep_attachments task hotovy: %s', stats)
    return stats
