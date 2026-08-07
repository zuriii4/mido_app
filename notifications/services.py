from inspect import Signature


from documents.services import get_required_users
from notifications.models import Notification
from users.models import User


def get_notifications(user):
    """
    Returns a queryset of notifications for the given user.
    """
    return Notification.objects.filter(user=user).order_by('-created_at')


def get_unread_notifications(user):
    """
    Returns a queryset of unread notifications for the given user.
    """
    return Notification.objects.filter(user=user, is_read=False).order_by('-created_at')


def mark_notification_as_read(user, pk):
    """
    Marks the given notification as read.
    """
    notification = Notification.objects.filter(user=user, pk=pk).first()
    if notification is None:
        return None
    notification.is_read = True
    notification.save(update_fields=['is_read', 'updated_at'])
    return notification


def create_notifications_for_document(document):
    """
    Creates notifications for all active users assigned to the current
    document version (cez DocumentAssignment).
    """
    current = document.current_version
    if current is None or not current.assignments.active_now().exists():
        return 0

    users = get_required_users(document)

    already_notified_ids = set(
        Notification.objects.filter(document=document).values_list('user_id', flat=True)
    )

    notifications = [
        Notification(
            user=user,
            document=document,
            message=f"Nový dokument '{document.title}' čaká na váš podpis.",
        )
        for user in users
        if user.id not in already_notified_ids
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)

    return len(notifications)


def get_signed_users_for_document(document):
    """
    Returns a queryset of users who have signed the given document.
    """

    if document.current_version is None:
        return User.objects.none()

    current = document.current_version
    if current is None:
        return User.objects.none()
    signed_users = User.objects.filter(
        signatures__document_version_id=current.pk
    ).distinct()
    return signed_users 

def get_unsigned_users_for_document(document):
    """
    Returns a queryset of users who have not signed the given document.
    """

    current = document.current_version
    if current is None or not current.assignments.active_now().exists():
        return User.objects.none()

    signed_users_ids = get_signed_users_for_document(document).values_list('id', flat=True)

    unsigned_users = get_required_users(document).exclude(
        pk__in=signed_users_ids
    )

    return unsigned_users



def create_reminder_notification_for_document(document):
    """
    Creates a reminder notification for all active users who have not signed the document.
    """
    already_notified_ids = set(
        Notification.objects.filter(document=document).values_list('user_id', flat=True)
    )

    unsigned_users = get_unsigned_users_for_document(document).exclude(
        pk__in=already_notified_ids
    )

    notifications = [
        Notification(
            user=user,
            document=document,
            message=f"Pripomienka: Dokument '{document.title}' čaká na váš podpis.",
        )
        for user in unsigned_users
    ]

    if notifications:
        Notification.objects.bulk_create(notifications)

    return len(notifications)