import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from rfid_auth.models import RfidSession

logger = logging.getLogger('rfid_auth')


def delete_stale_sessions(days=7):
    """Zmaze expirovane/revokovane RfidSession staršie ako `days` dni. Vracia pocet."""
    cutoff = timezone.now() - timezone.timedelta(days=days)
    stale = RfidSession.objects.filter(
        Q(expires_at__lt=cutoff) | Q(revoked_at__lt=cutoff)
    )
    count = stale.count()
    stale.delete()
    logger.info('cleanup_sessions: zmazanych %s neplatnych session-i', count)
    return count


@shared_task(name='rfid_auth.cleanup_sessions')
def cleanup_sessions_task(days=7):
    return delete_stale_sessions(days)
