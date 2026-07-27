# Project Context

Django REST backend for internal document signing system with RFID authentication.

## Stack
- Django 5.x + Django REST Framework
- PostgreSQL (dev: SQLite)
- Celery + Celery Beat + Redis (daily user sync, SharePoint sync)
- Custom User model: `users.User` (AUTH_USER_MODEL)

## Architecture
- Apps: `core`, `users`, `documents`, `signatures`, `rfid_auth`
- `core` — BaseModel (UUID pk, created_at, updated_at) — all models inherit from this
- `users` — User (rfid_uid, profession_code, business_unit FK), BusinessUnit (BU01-BU15), ProfessionCategory (profession_codes JSONField)
- `documents` — Document, DocumentVersion (signatures target THIS, not Document), DocumentVisibilityRule (rule_type: ALL/BUSINESS_UNIT/PROFESSION_CATEGORY/BOTH/USER_EXPLICIT, supports exclusions + time validity), Attachment (FK to DocumentVersion, never signed)
- `signatures` — Signature (user + document_version, unique_together, audit fields: rfid_uid_used, ip_address)
- `rfid_auth` — RFID login flow, custom auth backend

## Key Rules
- Signatures are ALWAYS on DocumentVersion, never on Document or Attachment directly
- New DocumentVersion resets signing requirement (is_current flag pattern)
- User deactivation via daily sync sets is_active=False, NEVER delete
- Document visibility resolved via DocumentVisibilityRule, not direct M:N fields
- Business logic belongs in services.py per app, not in views/models

## Commands
- `python manage.py makemigrations && python manage.py migrate`
- `python manage.py sync_users` — manual trigger for daily sync command

## Conventions
- Keep views/serializers thin, business logic in services.py
- Every FK relationship documented in model docstring
