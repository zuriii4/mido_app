import json
from django.core.management.base import BaseCommand
import notifications.tasks as notifications_tasks


class Command(BaseCommand):
    help = 'Posiela pripomienky na podpis dokumentov, ktore este neboli podpisane.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-number',
            type=str,
            default=None,
            help='Posiela pripomienky len pre dokument s danym cislom.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Len vypise co by sa stalo, nic neposiela.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if options['document_number']:
            document = notifications_tasks.get_document_by_number(options['document_number'])
            if document is None:
                self.stdout.write(self.style.ERROR(
                    f'Dokument s cislom "{options["document_number"]}" neexistuje.'
                ))
                return
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    f'[DRY-RUN] Vytvoril by som pripomienky pre dokument: {document.title}'
                ))
                return
            self.stdout.write(f'Odosielam pripomienky pre dokument: {document.title}')
            stats = notifications_tasks.send_reminder_notifications_for_document(document.id)
            self.stdout.write(self.style.SUCCESS(f'Vytvorenych {stats} notifikacii.'))
        else:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    '[DRY-RUN] Prechadzal by som vsetky aktivne dokumenty.'
                ))
                return
            self.stdout.write('Odosielam pripomienky pre vsetky dokumenty...')
            stats = notifications_tasks.send_reminders_task()
            self.stdout.write(self.style.SUCCESS(f'Spustene. Celkovy pocet: {stats}.'))
