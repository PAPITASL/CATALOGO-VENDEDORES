import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from catalogo.models import ModeloVehiculo
from catalogo.vehicle_safety import (
    TABLES, catalog_state, database_identity, file_hash, pending_changes, state_hash,
)


class Command(BaseCommand):
    help = 'Corrige exclusivamente los nombres aprobados por ID; conserva LOBO, anios y relaciones. Simula por defecto.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true')
        mode.add_argument('--apply', action='store_true')
        parser.add_argument('--backup-dir')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Requiere PostgreSQL.')
        apply = options['apply']
        backup_root = Path(options['backup_dir']).resolve() if options['backup_dir'] else None
        manifest = None
        if apply:
            if backup_root is None:
                raise CommandError('--apply requiere --backup-dir con respaldo verificado.')
            try:
                manifest = json.loads((backup_root / 'manifest.json').read_text(encoding='utf-8'))
                valid = (manifest['verified'] is True and manifest['database_identity'] == database_identity()
                         and file_hash(backup_root / 'database.dump') == manifest['dump_sha256']
                         and file_hash(backup_root / 'media.zip') == manifest['media_zip_sha256'])
            except (OSError, ValueError, KeyError) as error:
                raise CommandError('No se pudo verificar el respaldo.') from error
            if not valid:
                raise CommandError('Respaldo incorrecto o perteneciente a otra base. No se modifica nada.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '10s'")
                if apply:
                    cursor.execute('LOCK TABLE ' + ', '.join(f'"{table}"' for table in TABLES) + ' IN SHARE ROW EXCLUSIVE MODE')
                else:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            models = list(ModeloVehiculo.objects.select_related('marca').order_by('pk'))
            changes = pending_changes(models)
            plan = [{'id': model.pk, 'antes': old, 'despues': new, 'productos': model.productos.count()}
                    for model, old, new in changes]
            self.stdout.write(json.dumps(plan, ensure_ascii=False))
            if not apply or not changes:
                self.stdout.write('Solo simulacion.' if not apply else 'Sin cambios: los nombres ya estan corregidos.')
                return
            with connection.cursor() as cursor:
                before = catalog_state(cursor)
            if state_hash(before) != manifest['catalog_sha256']:
                raise CommandError('El catalogo cambio desde el respaldo. Genera uno nuevo antes de aplicar.')
            expected = deepcopy(before)
            name_index = expected['modelos_vehiculo']['columns'].index('nombre')
            id_index = expected['modelos_vehiculo']['columns'].index('id')
            replacements = {model.pk: new for model, old, new in changes}
            expected['modelos_vehiculo']['rows'] = [
                tuple(replacements.get(row[id_index], value) if i == name_index else value for i, value in enumerate(row))
                for row in expected['modelos_vehiculo']['rows']
            ]
            for model, old, new in changes:
                if ModeloVehiculo.objects.filter(pk=model.pk, nombre=old).update(nombre=new) != 1:
                    raise CommandError('El modelo cambio durante la aplicacion; se revierte la transaccion.')
            with connection.cursor() as cursor:
                after = catalog_state(cursor)
            if state_hash(after) != state_hash(expected):
                raise CommandError('Cambios inesperados en el catalogo. Se revierte toda la transaccion.')
            # Persist the rollback journal before commit. On any filesystem error PostgreSQL rolls back.
            journal = {'estado': 'verificado_antes_de_commit', 'cambios': plan,
                       'before_sha256': state_hash(before), 'after_sha256': state_hash(after),
                       'backup': str(backup_root), 'nota': 'Confirmar estado actual de los IDs antes de usar para revertir.'}
            journal_path = backup_root / ('applied-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
            journal_path.write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Aplicados {len(changes)} nombres. Todos los demas campos y relaciones del catalogo permanecen identicos. Registro: {journal_path}'))
