"""Narrow commercial year corrections corroborated by existing observations."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from catalogo.models import Producto
from catalogo.vehicle_safety import TABLES, catalog_state, database_identity, file_hash, state_hash


# ID, exact original name/observation/image, target years. No inferred fitments.
PERIOD_PLAN = (
    (301, 'MANIJAS INTERIORES DELANTERA PAR', 'SILVERADO 1995 - 1998',
     'productos/CHEVROLET_CK_SILVERADO_CHEYENNE_1988_1998_MANIJAS_INTERIORES.png', (1995, 1998)),
    (345, 'TABLERO ROJO', 'MODELOS: 1990 - 1994\r\nSOLAMENTE ROJO',
     'productos/CHEVROLET_CK_SILVERADO_CHEYENNE_1990_1994_CARATULA_TABLERO_BLANCO_ROJO.jpg', (1990, 1994)),
)


class Command(BaseCommand):
    help = 'Reconcilia solo los anios comerciales de productos 301 y 345; simula por defecto.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true')
        mode.add_argument('--apply', action='store_true')
        parser.add_argument('--backup-dir')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Requiere PostgreSQL.')
        apply = options['apply']
        root = Path(options['backup_dir']).resolve() if options['backup_dir'] else None
        manifest = None
        if apply:
            if root is None:
                raise CommandError('--apply requiere --backup-dir.')
            try:
                manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
                valid = (manifest['verified'] is True and manifest['database_identity'] == database_identity()
                         and file_hash(root / 'database.dump') == manifest['dump_sha256']
                         and file_hash(root / 'media.zip') == manifest['media_zip_sha256'])
            except (OSError, KeyError, ValueError) as error:
                raise CommandError('No se puede verificar el respaldo.') from error
            if not valid:
                raise CommandError('Respaldo incorrecto. No se modifica nada.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '10s'")
                if apply:
                    cursor.execute('LOCK TABLE ' + ', '.join(f'"{table}"' for table in TABLES) + ' IN SHARE ROW EXCLUSIVE MODE')
                else:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            products = {p.pk: p for p in Producto.objects.filter(pk__in=[row[0] for row in PERIOD_PLAN]).select_related('modelo__marca')}
            changes = []
            for pk, name, notes, image, years in PERIOD_PLAN:
                p = products.get(pk)
                if (p is None or p.modelo_id != 9 or p.modelo.nombre != 'C/K SILVERADO / CHEYENNE'
                        or p.modelo.marca.nombre != 'CHEVROLET' or (p.modelo.anio_inicio, p.modelo.anio_fin) != (1988, 1998)
                        or (p.nombre_pieza, p.observaciones, p.imagen_principal.name) != (name, notes, image)):
                    raise CommandError(f'Identidad/evidencia del producto {pk} distinta del plan. No se modifica nada.')
                original = (p.anio_inicio, p.anio_fin)
                if original not in ((1988, 1998), years):
                    raise CommandError(f'Los anios del producto {pk} cambiaron desde la auditoria.')
                if original != years:
                    changes.append({'id': pk, 'modelo_id': 9, 'antes': original, 'despues': years})
            self.stdout.write(json.dumps(changes))
            if not apply or not changes:
                self.stdout.write('Solo simulacion.' if not apply else 'Sin cambios: los periodos ya estan corregidos.')
                return
            with connection.cursor() as cursor:
                before = catalog_state(cursor)
            if state_hash(before) != manifest['catalog_sha256']:
                raise CommandError('El catalogo cambio desde el respaldo. Generar uno nuevo.')
            expected = deepcopy(before)
            columns = expected['productos']['columns']
            id_col, start_col, end_col = (columns.index(field) for field in ('id', 'anio_inicio', 'anio_fin'))
            targets = {row['id']: row['despues'] for row in changes}
            expected_rows = []
            for record in expected['productos']['rows']:
                values = list(record)
                if values[id_col] in targets:
                    values[start_col], values[end_col] = targets[values[id_col]]
                expected_rows.append(tuple(values))
            expected['productos']['rows'] = expected_rows
            for row in changes:
                count = Producto.objects.filter(pk=row['id'], modelo_id=9, anio_inicio=row['antes'][0], anio_fin=row['antes'][1]).update(
                    anio_inicio=row['despues'][0], anio_fin=row['despues'][1])
                if count != 1:
                    raise CommandError('Cambio concurrente. Se revierte toda la transaccion.')
            with connection.cursor() as cursor:
                after = catalog_state(cursor)
            if state_hash(after) != state_hash(expected):
                raise CommandError('Cambios inesperados. Se revierte toda la transaccion.')
            journal = {'estado': 'verificado_antes_de_commit', 'cambios': changes,
                       'before_sha256': state_hash(before), 'after_sha256': state_hash(after),
                       'alcance': 'Reconciliacion de anios comerciales con observaciones existentes; no certificacion OEM.'}
            path = root / ('product-periods-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
            path.write_text(json.dumps(journal, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Aplicados {len(changes)} periodos de producto. Otros campos y relaciones identicos. Registro: {path}'))
