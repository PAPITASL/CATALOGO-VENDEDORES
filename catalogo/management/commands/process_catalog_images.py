import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from catalogo.clean_images import process_next_image


class Command(BaseCommand):
    help = 'Process the independent clean catalog image queue.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Process at most one image and exit.')

    def handle(self, *args, **options):
        self.stdout.write('Procesador de imágenes de catálogo iniciado.')
        try:
            while True:
                close_old_connections()
                processed = process_next_image()
                if options['once']:
                    return
                if not processed:
                    time.sleep(3)
        except KeyboardInterrupt:
            self.stdout.write('Procesador detenido.')
