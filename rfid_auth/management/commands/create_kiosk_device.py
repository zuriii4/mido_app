from django.core.management.base import BaseCommand

from rfid_auth.models import KioskDevice


class Command(BaseCommand):
    help = 'Vytvori novy kiosk device a vypise jeho token (zobrazi sa len raz, ulozi sa hashovane nikde - je to bearer secret).'

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True)
        parser.add_argument('--location', default='')

    def handle(self, *args, **options):
        device = KioskDevice.objects.create(name=options['name'], location=options['location'])
        self.stdout.write(self.style.SUCCESS(f'Kiosk "{device.name}" vytvoreny.'))
        self.stdout.write(f'X-Device-Token: {device.token}')
