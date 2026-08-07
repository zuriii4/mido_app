from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from documents.models import Document, DocumentAssignment, DocumentVersion


def _time_window_q(now):
    """Pravidlo je ucinne, ak now spada do [valid_from, valid_to] (null = bez hranice)."""
    return (
        (Q(valid_from__isnull=True) | Q(valid_from__lte=now))
        & (Q(valid_to__isnull=True) | Q(valid_to__gte=now))
    )


def _assignment_matches_user_q(user):
    """Q nad DocumentAssignment: priradenie sa vztahuje na tohto pouzivatela."""
    match = Q(target_type=DocumentAssignment.TARGET_ALL)
    match |= Q(target_type=DocumentAssignment.TARGET_USER, users=user)
    if user.business_unit_id is not None:
        match |= Q(
            target_type=DocumentAssignment.TARGET_BUSINESS_UNIT,
            business_units=user.business_unit_id,
        )
    if user.profession_code_id is not None:
        match |= Q(
            target_type=DocumentAssignment.TARGET_PROFESSION_CATEGORY,
            profession_categories=user.profession_code_id,
        )
    if user.business_unit_id is not None and user.profession_code_id is not None:
        match |= Q(
            target_type=DocumentAssignment.TARGET_BOTH,
            business_units=user.business_unit_id,
            profession_categories=user.profession_code_id,
        )
    return match


def get_visible_documents(user):
    """Aktivne dokumenty, ktore ma dany pouzivatel vidiet""" 
    now = timezone.now()

    assignments = DocumentAssignment.objects.filter(
        document_version__document=OuterRef('pk'),
        document_version__is_current=True,
    ).filter(_time_window_q(now))
    matching_assignments = assignments.filter(_assignment_matches_user_q(user))

    return (
        Document.objects
        .filter(is_active=True)
        .annotate(
            _has_assignments=Exists(assignments),
            _matches_assignment=Exists(matching_assignments),
        )
        .filter(Q(_matches_assignment=True))
    )


def get_unsigned_documents(user):
    """Viditelne dokumenty, ktorych aktualnu verziu pouzivatel este nepodpisal.
    Vylucuje dokumenty, ktorych aktualna verzia este nema stiahnuty subor
    (kiosk nikdy neukaze neotvoritelny dokument)."""
    from signatures.models import Signature

    current_with_file = DocumentVersion.objects.filter(
        document=OuterRef('pk'), is_current=True
    ).exclude(file_path='')
    signed_current = Signature.objects.filter(
        user=user,
        document_version__document=OuterRef('pk'),
        document_version__is_current=True,
    )
    return (
        get_visible_documents(user)
        .annotate(
            _has_file=Exists(current_with_file),
            _signed=Exists(signed_current),
        )
        .filter(_has_file=True, _signed=False)
    )


def get_required_users(document):
    """Aktivni pouzivatelia, ktorym je priradena aktualna verzia dokumentu
    (pre reporty 'kto este nepodpisal')."""
    from users.models import User

    users = User.objects.filter(is_active=True).order_by('lastname', 'firstname')

    current = document.current_version
    if current is not None and current.assignments.active_now().exists():
        users = DocumentAssignment.get_assigned_users(current).order_by(
            'lastname', 'firstname')

    return users

