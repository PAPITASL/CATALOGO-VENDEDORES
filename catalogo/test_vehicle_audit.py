from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from catalogo.management.commands.audit_vehicle_models import audit
from catalogo.vehicle_safety import state_hash


def vehicle(pk, name, start=1992, end=1998, brand=1):
    return dict(id=pk, marca_id=brand, nombre=name, anio_inicio=start, anio_fin=end)


class VehicleAuditTests(SimpleTestCase):
    brands = [dict(id=1, nombre='CHEVROLET'), dict(id=2, nombre='HONDA'), dict(id=3, nombre='FORD')]

    def test_backup_comparison_preserves_same_instant_across_session_timezones(self):
        utc = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
        local = utc.astimezone(timezone(timedelta(hours=-5)))
        self.assertEqual(state_hash({'time': utc}), state_hash({'time': local}))

    def test_overlap_is_inclusive_and_never_a_merge(self):
        models = [vehicle(1, 'SILVERADO', 1992, 1998), vehicle(2, 'SILVERADO', 1998, 2000),
                  vehicle(3, 'SILVERADO', 2001, 2002)]
        report = audit(self.brands, models, [])
        self.assertEqual(report['superposiciones'], [[1, 2]])
        self.assertTrue(all(row['estado'] == 'conservar' for row in report['modelos']))

    def test_alias_collision_keeps_ids_products_and_original_values(self):
        models = [vehicle(10, ' CRV ', 2012, 2016, 2), vehicle(11, 'CR-V', 2012, 2016, 2)]
        products = [dict(id=100, modelo_id=10, anio_inicio=2012, anio_fin=2016,
                         imagen_principal='productos/original.jpg', observaciones='Original', precio_venta='99.00')]
        original = deepcopy((models, products))
        report = audit(self.brands, models, products)
        self.assertEqual(report['modelos'][0]['conflictos_destino'], [11])
        self.assertEqual(report['modelos'][0]['productos'][0], products[0])
        self.assertEqual(report['duplicados_o_colisiones_propuestas'], [[10, 11]])
        self.assertEqual((models, products), original)
        self.assertEqual(audit(self.brands, models, products), report)

    def test_missing_years_are_uncertain_not_assumed_compatible(self):
        report = audit(self.brands, [vehicle(1, 'SILVERADO', None, None), vehicle(2, 'SILVERADO')], [])
        self.assertEqual(report['superposiciones'], [])
        self.assertEqual(report['rangos_incompletos_para_comparar'], [[1, 2]])

    def test_same_name_different_brand_is_not_duplicate(self):
        report = audit(self.brands, [vehicle(1, 'TEST'), vehicle(2, 'TEST', brand=2)], [])
        self.assertEqual(report['duplicados_o_colisiones_propuestas'], [])
        self.assertEqual(report['superposiciones'], [])

    def test_chevrolet_family_and_product_years_require_manual_review(self):
        report = audit(self.brands, [vehicle(1, 'SILVEADO'), vehicle(2, 'CK SILVERADO CHEYENNE')],
                       [dict(id=10, modelo_id=1, anio_inicio=1990, anio_fin=1999)])
        self.assertEqual(report['superposiciones_familia_chevrolet_para_revision_no_fusion'], [[1, 2]])
        self.assertEqual(report['modelos'][0]['productos_fuera_del_rango'], [10])
        self.assertEqual(report['modelos'][0]['estado'], 'pendiente_revision')

    def test_lobo_requires_variant_evidence(self):
        report = audit(self.brands, [vehicle(1, 'F150_LOBO', brand=3)], [])
        self.assertEqual(report['modelos'][0]['estado'], 'pendiente_revision')
        self.assertIn('variante', report['modelos'][0]['motivo'])

    def test_command_refuses_backend_without_readonly_guarantee(self):
        with patch('catalogo.management.commands.audit_vehicle_models.connection') as conn:
            conn.vendor = 'sqlite'
            with self.assertRaisesMessage(CommandError, 'requiere PostgreSQL'):
                call_command('audit_vehicle_models', dry_run=True, stdout=StringIO())
            conn.cursor.assert_not_called()
