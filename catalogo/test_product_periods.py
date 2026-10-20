import json
import uuid
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.management import CommandError, call_command
from django.db import connection
from django.http import HttpResponse
from django.test import RequestFactory, TransactionTestCase

from catalogo.management.commands.normalize_product_periods import PERIOD_PLAN
from catalogo.models import Marca, ModeloVehiculo, Producto
from catalogo.vehicle_safety import catalog_state, database_identity, file_hash, state_hash
from catalogo.views import vehicle_selector


class ProductPeriodTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL required')
        brand = Marca.objects.create(nombre='CHEVROLET')
        model = ModeloVehiculo.objects.create(pk=9, marca=brand, nombre='C/K SILVERADO / CHEYENNE', anio_inicio=1988, anio_fin=1998)
        for pk, name, notes, image, years in PERIOD_PLAN:
            Producto.objects.create(pk=pk, modelo=model, nombre_pieza=name, observaciones=notes, imagen_principal=image,
                                    anio_inicio=1988, anio_fin=1998, precio_minimo=10, precio_venta=20)
        self.root = Path(settings.BASE_DIR) / '.vehicle-audit' / ('test-periods-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(self.cleanup_files)
        for name in ('database.dump', 'media.zip'):
            (self.root / name).write_bytes(b'fixture')
        with connection.cursor() as cursor:
            self.before = catalog_state(cursor)
        manifest = dict(verified=True, database_identity=database_identity(), catalog_sha256=state_hash(self.before),
                        dump_sha256=file_hash(self.root / 'database.dump'), media_zip_sha256=file_hash(self.root / 'media.zip'))
        (self.root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def cleanup_files(self):
        self.root.resolve().relative_to((Path(settings.BASE_DIR) / '.vehicle-audit').resolve())
        for path in self.root.iterdir():
            path.unlink()
        self.root.rmdir()

    def apply(self):
        call_command('normalize_product_periods', apply=True, backup_dir=str(self.root), stdout=StringIO())

    def test_only_years_change_with_correct_public_filter_boundaries_and_idempotence(self):
        original = list(Producto.objects.order_by('pk').values())
        self.apply()
        actual = list(Producto.objects.order_by('pk').values())
        self.assertEqual((actual[0]['anio_inicio'], actual[0]['anio_fin']), (1995, 1998))
        self.assertEqual((actual[1]['anio_inicio'], actual[1]['anio_fin']), (1990, 1994))
        for old, new in zip(original, actual):
            self.assertEqual({k:v for k,v in old.items() if k not in ('anio_inicio', 'anio_fin')},
                             {k:v for k,v in new.items() if k not in ('anio_inicio', 'anio_fin')})
        model = ModeloVehiculo.objects.get(pk=9)
        self.assertEqual((model.anio_inicio, model.anio_fin), (1988, 1998))
        for year, expected in ((1989, []), (1990, [345]), (1994, [345]), (1995, [301]), (1998, [301])):
            request = RequestFactory().get('/')
            request.user = AnonymousUser()
            with patch('catalogo.views.render', return_value=HttpResponse()) as render:
                vehicle_selector(request, marca_id=model.marca_id, modelo_id=9, anio=year)
                self.assertEqual(list(render.call_args.args[2]['products'].values_list('pk', flat=True)), expected)
        self.apply()
        self.assertEqual(actual, list(Producto.objects.order_by('pk').values()))
        self.assertEqual(len(list(self.root.glob('product-periods-*.json'))), 1)

    def test_dry_run_does_not_write(self):
        call_command('normalize_product_periods', dry_run=True, stdout=StringIO())
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), self.before)

    def test_changed_evidence_aborts_every_update(self):
        Producto.objects.filter(pk=345).update(observaciones='Aplicacion distinta')
        with self.assertRaisesMessage(CommandError, 'evidencia'):
            self.apply()
        self.assertEqual(Producto.objects.get(pk=301).anio_inicio, 1988)

    def test_journal_failure_rolls_back_both_products(self):
        with patch.object(Path, 'write_text', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                self.apply()
        with connection.cursor() as cursor:
            self.assertEqual(catalog_state(cursor), self.before)
