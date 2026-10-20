"""Read-only vehicle audit. Deliberately provides no apply option."""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from catalogo.models import Categoria, Marca, ModeloVehiculo, Producto


ALIASES = {
    ('FORD', 'F150_LOBO'): ('F-150', 'Confirmar Ford Lobo y conservar la variante comercial; no hay campo de variante.'),
    ('FORD', '150 BRONCO'): ('BRONCO', 'Confirmar que sea Bronco y revisar los productos.'),
    ('CHEVROLET', 'SILVEADO'): ('C/K SILVERADO', 'Confirmar carroceria C/K por pieza; no basta la similitud del nombre.'),
    ('CHEVROLET', 'CK SILVERADO CHEYENNE'): ('C/K SILVERADO / CHEYENNE', 'Correccion de escritura; revisar colisiones antes de aprobar.'),
    ('HONDA', 'CRV'): ('CR-V', 'Correccion de escritura; conservar todos los anios y relaciones.'),
}


def normalized(value):
    return ' '.join(value.split()).upper()


def audit(brands, models, products):
    brand_names = {row['id']: row['nombre'] for row in brands}
    by_model = defaultdict(list)
    for product in products:
        by_model[product['modelo_id']].append(product)
    rows, groups, families = [], defaultdict(list), defaultdict(list)
    for model in models:
        brand = brand_names[model['marca_id']]
        name = normalized(model['nombre'])
        proposal = ALIASES.get((normalized(brand), name))
        target = proposal[0] if proposal else model['nombre']
        linked = by_model[model['id']]
        collisions = [other['id'] for other in models if other['id'] != model['id']
                      and other['marca_id'] == model['marca_id']
                      and normalized(other['nombre']) == normalized(target)
                      and (other['anio_inicio'], other['anio_fin']) == (model['anio_inicio'], model['anio_fin'])]
        rows.append({
            **model, 'marca_nombre': brand, 'nombre_propuesto': target,
            'estado': 'pendiente_revision' if proposal else 'conservar',
            'motivo': proposal[1] if proposal else 'Sin correccion automatica ni cambio de compatibilidad.',
            'conflictos_destino': collisions,
            'productos_afectados': len(linked) if proposal else 0,
            'productos': linked,
            'productos_fuera_del_rango': [p['id'] for p in linked if
                (model['anio_inicio'] is not None and p['anio_inicio'] < model['anio_inicio']) or
                (model['anio_fin'] is not None and p['anio_fin'] > model['anio_fin'])],
        })
        # Group spelling candidates to reveal conflicts before any future rename.
        groups[(model['marca_id'], normalized(target))].append(model)
        if normalized(brand) == 'CHEVROLET' and ('SILVERADO' in name or name == 'SILVEADO'):
            families[model['marca_id']].append(model)
    overlaps, duplicates, unknown = [], [], []
    for group in groups.values():
        for first, second in combinations(group, 2):
            pair = [first['id'], second['id']]
            a, b = first['anio_inicio'], first['anio_fin']
            c, d = second['anio_inicio'], second['anio_fin']
            if (a, b) == (c, d):
                duplicates.append(pair)
            if None in (a, b, c, d):
                unknown.append(pair)
            elif max(a, c) <= min(b, d):
                overlaps.append(pair)
    family_overlaps = []
    for group in families.values():
        for first, second in combinations(group, 2):
            years = (first['anio_inicio'], first['anio_fin'], second['anio_inicio'], second['anio_fin'])
            if None not in years and max(years[0], years[2]) <= min(years[1], years[3]):
                family_overlaps.append([first['id'], second['id']])
    return {'modelos': rows, 'duplicados_o_colisiones_propuestas': duplicates,
            'superposiciones': overlaps, 'rangos_incompletos_para_comparar': unknown,
            'superposiciones_familia_chevrolet_para_revision_no_fusion': family_overlaps,
            'rangos_invalidos': [m['id'] for m in models if m['anio_inicio'] is not None and m['anio_fin'] is not None and m['anio_inicio'] > m['anio_fin']],
            'productos_sin_modelo_en_snapshot': [p['id'] for p in products if p['modelo_id'] not in {m['id'] for m in models}],
            'resumen': {'marcas': len(brands), 'modelos': len(models), 'productos': len(products),
                        'propuestas_nombre': sum(row['estado'] == 'pendiente_revision' for row in rows)},
            'politica': 'Solo simulacion. No fusionar, dividir, ampliar anios ni modificar registros. Compatibilidad pendiente de evidencia por pieza.'}


class Command(BaseCommand):
    help = 'Audita vehiculos y exporta un snapshot verificable, sin modificar datos.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Explicito; este comando siempre es de solo lectura.')
        parser.add_argument('--output-dir', default='.vehicle-audit')

    def handle(self, *args, **options):
        # PostgreSQL prevents accidental writes and gives every query the same snapshot.
        if connection.vendor != 'postgresql':
            raise CommandError('Esta auditoria requiere PostgreSQL para garantizar un snapshot de solo lectura consistente.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                actual_tables = set(connection.introspection.table_names(cursor))
                expected_tables = {m._meta.db_table for m in (Marca, ModeloVehiculo, Categoria, Producto)}
                if not expected_tables <= actual_tables:
                    raise CommandError('Faltan tablas del catalogo; no se puede auditar de forma segura.')
                constraints = {table: connection.introspection.get_constraints(cursor, table)
                               for table in sorted(expected_tables)}
            brands = list(Marca.objects.order_by('pk').values())
            categories = list(Categoria.objects.order_by('pk'))
            models = list(ModeloVehiculo.objects.order_by('pk').values())
            products = list(Producto.objects.order_by('pk').values())
            # Includes complete rows, prices, observations, image paths and original FKs.
            snapshot = serializers.serialize('json', [
                *Marca.objects.order_by('pk'), *categories,
                *ModeloVehiculo.objects.order_by('pk'), *Producto.objects.order_by('pk'),
            ], indent=2).encode('utf-8')
            report = audit(brands, models, products)
            report['restricciones_reales'] = constraints
            report['relaciones_django'] = [
                {'tabla': relation.related_model._meta.db_table, 'campo': relation.field.name,
                 'on_delete': relation.field.remote_field.on_delete.__name__}
                for relation in ModeloVehiculo._meta.related_objects
            ]
        root = Path(options['output_dir']) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        root.mkdir(parents=True, exist_ok=False)
        snapshot_path = root / 'snapshot.json'
        snapshot_path.write_bytes(snapshot)
        digest = hashlib.sha256(snapshot).hexdigest()
        if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != digest:
            raise CommandError('No se pudo verificar el snapshot; no usarlo para restaurar.')
        decoded = json.loads(snapshot_path.read_text(encoding='utf-8'))
        expected_counts = {'catalogo.marca': len(brands), 'catalogo.categoria': len(categories),
                           'catalogo.modelovehiculo': len(models), 'catalogo.producto': len(products)}
        if any(sum(row['model'] == label for row in decoded) != count for label, count in expected_counts.items()):
            raise CommandError('El conteo del snapshot no coincide.')
        model_ids = {row['pk'] for row in decoded if row['model'] == 'catalogo.modelovehiculo'}
        brand_ids = {row['pk'] for row in decoded if row['model'] == 'catalogo.marca'}
        if any(row['fields']['modelo'] not in model_ids for row in decoded if row['model'] == 'catalogo.producto') or any(
            row['fields']['marca'] not in brand_ids for row in decoded if row['model'] == 'catalogo.modelovehiculo'
        ):
            raise CommandError('El snapshot contiene relaciones incompletas.')
        report['snapshot_sha256'] = digest
        report['alcance_snapshot'] = 'Registros de marcas, categorias, modelos y productos. No incluye archivos de imagen ni otras tablas; no sustituye un backup integral de PostgreSQL y media.'
        (root / 'report.json').write_text(json.dumps(report, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False), encoding='utf-8')
        (root / 'snapshot.sha256').write_text(f'{digest}  snapshot.json\n', encoding='ascii')
        self.stdout.write(json.dumps(report['resumen'], ensure_ascii=False))
        self.stdout.write(self.style.SUCCESS(f'Solo lectura. Snapshot SHA-256 verificado. Informe: {root / "report.json"}'))
