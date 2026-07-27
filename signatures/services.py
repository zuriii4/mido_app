"""
Logika podpisovania (PLAN.md sekcia E/I-9).

Podpis = proof-of-presence: pouzivatel uz ma platnu RFID session (Bearer token),
ale podpis vyzaduje OPATOVNE fyzicke prilozenie karty na kiosku. Server overi,
ze rfid_uid z re-tapu patri prave prihlasenemu pouzivatelovi.
"""
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from documents.services import get_visible_documents
from signatures.models import Signature


class AlreadySigned(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Tuto verziu dokumentu ste uz podpisali.'
    default_code = 'already_signed'


def create_signature(user, document_version, rfid_uid, ip_address=None, device=None):
    """Vytvori podpis. Poradie kontrol:
    1. re-tap RFID nesedi s prihlasenym pouzivatelom -> 403, BEZ zaznamu,
    2. neaktualna verzia / neaktivny alebo neviditelny dokument -> 400,
    3. duplicitny podpis -> 409 (unique_together user+document_version).
    """
    if not rfid_uid or rfid_uid != user.rfid_uid:
        raise PermissionDenied('RFID karta nepatri prihlasenemu pouzivatelovi.')

    if not document_version.is_current:
        raise ValidationError('Tato verzia dokumentu uz nie je aktualna.')

    document = document_version.document
    if not document.is_active or not get_visible_documents(user).filter(pk=document.pk).exists():
        raise ValidationError('Dokument nie je dostupny na podpis.')

    try:
        with transaction.atomic():
            return Signature.objects.create(
                user=user,
                document_version=document_version,
                rfid_uid_used=rfid_uid,
                ip_address=ip_address,
                device_id=device.name if device is not None else '',
            )
    except IntegrityError:
        raise AlreadySigned()
