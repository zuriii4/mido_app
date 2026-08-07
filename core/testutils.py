"""Zdielane helpery pre testy (users, documents, rfid sessions)."""
import itertools
from datetime import timedelta

from django.core.files.base import ContentFile
from django.utils import timezone
from rest_framework.test import APIClient

from documents.models import Document, DocumentVersion
from rfid_auth.models import RfidSession
from users.models import User

_seq = itertools.count(1)


def make_user(**kwargs):
    n = next(_seq)
    defaults = {
        'username': f'user{n}',
        'firstname': 'Jan',
        'lastname': f'Novak{n}',
        'rfid_uid': f'RFID-{n:04d}',
        'external_id': f'EXT-{n:04d}',
    }
    defaults.update(kwargs)
    return User.objects.create(**defaults)


def make_document(title=None, with_file=True, version_kwargs=None, **kwargs):
    """Vytvori dokument s aktualnou verziou; with_file=True ulozi aj PDF snapshot."""
    n = next(_seq)
    kwargs.setdefault('document_number', f'DOC-{n:04d}')
    document = Document.objects.create(title=title or f'Dokument {n}', **kwargs)
    vkwargs = {'version_label': '-', 'is_current': True}
    vkwargs.update(version_kwargs or {})
    version = DocumentVersion.objects.create(document=document, **vkwargs)
    if with_file:
        version.file_path.save(f'{document.pk}_v-.pdf', ContentFile(b'%PDF-1.4 test'), save=True)
    return document


def make_assignment(document, target_type, business_units=(), profession_categories=(), users=()):
    """Vytvori priradenie dokumentu na jeho aktualnu verziu."""
    from documents.models import DocumentAssignment
    assignment = DocumentAssignment.objects.create(
        document_version=document.current_version,
        target_type=target_type,
    )
    if business_units:
        assignment.business_units.set(business_units)
    if profession_categories:
        assignment.profession_categories.set(profession_categories)
    if users:
        assignment.users.set(users)
    return assignment


def make_session(user, device=None, ttl_minutes=10):
    return RfidSession.objects.create(
        user=user,
        device=device,
        expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
    )


def auth_client(user, device=None):
    """APIClient prihlaseny ako user cez RFID session Bearer token."""
    session = make_session(user, device=device)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {session.token}')
    return client
