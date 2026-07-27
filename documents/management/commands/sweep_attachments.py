import json

from django.core.management.base import BaseCommand

from documents.sync import sweep_attachments


class Command(BaseCommand):
    help = (
        'Prejde vsetky aktivne dokumenty a zosynchronizuje ich prilohy (acLibPrilohy) '
        'nezavisle od toho, ci sa zmenil etag dokumentu samotneho.'
    )

    def handle(self, *args, **options):
        stats = sweep_attachments()
        self.stdout.write(self.style.SUCCESS(json.dumps(stats, ensure_ascii=False)))