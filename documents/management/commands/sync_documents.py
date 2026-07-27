import json

from django.core.management.base import BaseCommand

from documents.sync import sync_documents


class Command(BaseCommand):
    help = 'Synchronizuje dokumenty (a ich prilohy) z acLibPlatne/acLibPrilohy zo SharePointu.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Spracuje len prvych N poloziek (na rychle overenie, nerobi deaktivaciu chybajucich).',
        )

    def handle(self, *args, **options):
        stats = sync_documents(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(json.dumps(stats, ensure_ascii=False)))
