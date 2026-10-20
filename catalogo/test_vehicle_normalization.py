import json
import uuid
from copy import deepcopy
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.conf import settings
from django.db import connection
from django.test import TransactionTestCase

from catalogo.models import Marca, ModeloVehiculo, Producto
from catalogo.vehicle_safety import PLAN, catalog_state, database_identity, file_hash, state_hash


class VehicleNormalizationTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL transaction and lock verification')
        brands = {name: Marca.objects.create(nombre=name) for name in ('FORD', 'HONDA', 'CHEVROLET')}
        for pk, brand, old, new, start, end in PLAN:
            model = ModeloVehiculo.objects.create(pk=pk, marca=brands[brand], nombre=old,
                                                  anio_inicio=start, anio_fin=end)
            Producto.objects.create(modelo=model, nombre_pieza='ORIGINAL', anio_inicio=start, anio_fin=end,
                                    precio_minimo=10, precio_venta=20, imagen_principal='productos/original.jpg',
                                    observaciones='NO CAMBIAR')
        self.root = Path(settings.BASE_DIR) / '.vehicle-audit' / ('tests-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(self.cleanup_files)
        (self.root / 'database.dump').write_bytes(b'unit-test-backup')
        (self.root / 'media.zip').write_bytes(b'unit-test-media')
        self.refresh_manifest()

    def cleanup_files(self):
        self.root.resolve().relative_to((Path(settings.BASE_DIR) / '.vehicle-audit').resolve())
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()

    def refresh_manifest(self):
        with connection.cursor() as cursor:
            self.original = catalog_state(cursor)
        self.manifest = dict(verified=True, database_identity=database_identity(),
                             catalog_sha256=state_hash(self.original),
                             dump_sha256=file_hash(self.root / 'database.dump'),
                             media_zip_sha256=file_hash(self.root / 'media.zip'))
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def apply(self):
        return call_command('normalize_vehicle_names', apply=True, backup_dir=str(self.root), stdout=StringIO())

    def test_apply_changes_only_names_and_second_run_is_idempotent(self):
        self.apply()
        for pk, brand, old, new, start, end in PLAN:
            self.assertEqual(ModeloVehiculo.objects.get(pk=pk).nombre, new)
        with connection.cursor() as cursor:
            after = catalog_state(cursor)
        for table in ('marcas', 'categorias', 'productos'):
            self.assertEqual(self.original[table], after[table])
        columns = after['modelos_vehiculo']['columns']
        for before_row, after_row in zip(self.original['modelos_vehiculo']['rows'], after['modelos_vehiculo']['rows']):
            for index, column in enumerate(columns):
                if column != 'nombre':
                    self.assertEqual(before_row[index], after_row[index])
        self.apply()
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), after)
        self.assertEqual(len(list(self.root.glob('applied-*.json'))), 1)

    def test_dry_run_does_not_change_rows(self):
        call_command('normalize_vehicle_names', dry_run=True, stdout=StringIO())
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), self.original)

    def test_rejects_backup_from_changed_catalog(self):
        Producto.objects.update(observaciones='CAMBIO POSTERIOR')
        with self.assertRaisesMessage(CommandError, 'cambio desde el respaldo'):
            self.apply()
        self.assertEqual(ModeloVehiculo.objects.get(pk=4).nombre, '150 BRONCO')

    def test_rejects_corrupted_backup(self):
        (self.root / 'database.dump').write_bytes(b'changed')
        with self.assertRaisesMessage(CommandError, 'Respaldo incorrecto'):
            self.apply()

    def test_rejects_destination_collision(self):
        model = ModeloVehiculo.objects.get(pk=4)
        ModeloVehiculo.objects.create(pk=1000, marca=model.marca, nombre='BRONCO', anio_inicio=1992, anio_fin=1996)
        self.refresh_manifest()
        with self.assertRaisesMessage(CommandError, 'Conflicto'):
            self.apply()

    def test_rejects_changed_identity(self):
        ModeloVehiculo.objects.filter(pk=4).update(anio_inicio=1993)
        self.refresh_manifest()
        with self.assertRaisesMessage(CommandError, 'no coincide'):
            self.apply()

    def test_unexpected_after_state_rolls_back_all_updates(self):
        invalid = deepcopy(self.original)
        invalid['productos']['rows'] = []
        with patch('catalogo.management.commands.normalize_vehicle_names.catalog_state', side_effect=[self.original, invalid]):
            with self.assertRaisesMessage(CommandError, 'Cambios inesperados'):
                self.apply()
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), self.original)

    def test_journal_failure_rolls_back_all_updates(self):
        with patch.object(Path, 'write_text', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.apply()
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), self.original)

    def test_second_batch_preserves_first_batch_and_unapproved_ranges(self):
        for pk, brand, old, new, start, end in PLAN[:4]:
            ModeloVehiculo.objects.filter(pk=pk).update(nombre=new)
        chevrolet = Marca.objects.get(nombre='CHEVROLET')
        untouched = ModeloVehiculo.objects.create(pk=1001, marca=chevrolet, nombre='SILVERADO',
                                                  anio_inicio=1990, anio_fin=1998)
        self.refresh_manifest()
        self.apply()
        journal = json.loads(next(self.root.glob('applied-*.json')).read_text(encoding='utf-8'))
        self.assertEqual({row['id'] for row in journal['cambios']}, {1, 2, 8, 12, 13, 14, 15, 32})
        for pk in (1, 2, 8, 12, 13, 14, 15):
            self.assertEqual(ModeloVehiculo.objects.get(pk=pk).nombre, 'F-150 / LOBO')
        typo = ModeloVehiculo.objects.get(pk=32)
        self.assertEqual((typo.nombre, typo.anio_inicio, typo.anio_fin), ('SILVERADO', 1992, 1994))
        untouched.refresh_from_db()
        self.assertEqual((untouched.nombre, untouched.anio_inicio, untouched.anio_fin), ('SILVERADO', 1990, 1998))
