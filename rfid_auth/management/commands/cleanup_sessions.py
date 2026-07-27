"""Zmaze uz neplatne RFID session-y (expirovane alebo revokovane).

RfidSession je len docasny prihlasovaci token, nie audit zaznam (tym su podpisy),
takze sa da bezpecne mazat. Necha si `--days` dni stare zaznamy pre pripadny debug.

Spustanie: `python manage.py cleanup_sessions` (napr. z crontabu / Celery beat).
"""
from django.core.management.base import BaseCommand

from rfid_auth.tasks import delete_stale_sessions


class Command(BaseCommand):
    help = 'Zmaze expirovane a revokovane RFID session-y staršie ako --days dni.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='Ponechaj neplatne session-y mladsie ako tolko dni (default 7).',
        )

    def handle(self, *args, **options):
        count = delete_stale_sessions(days=options['days'])
        self.stdout.write(self.style.SUCCESS(f'Zmazanych {count} session-i.'))