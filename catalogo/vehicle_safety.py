"""Checks shared by vehicle backup and the narrowly approved spelling changes."""
import hashlib
import json
from datetime import datetime, timezone

from django.core.management.base import CommandError
from django.db import connection

TABLES = ('marcas', 'categorias', 'modelos_vehiculo', 'productos')
PLAN = (
    (4, 'FORD', '150 BRONCO', 'BRONCO', 1992, 1996),
    (16, 'FORD', '150 BRONCO', 'BRONCO', 1987, 1991),
    (25, 'HONDA', 'CRV', 'CR-V', 2012, 2016),
    (9, 'CHEVROLET', 'CK SILVERADO CHEYENNE', 'C/K SILVERADO / CHEYENNE', 1988, 1998),
    (1, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 1997, 2003),
    (2, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2004, 2008),
    (8, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2009, 2014),
    (12, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2015, 2017),
    (13, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2018, 2020),
    (14, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2021, 2023),
    (15, 'FORD', 'F150_LOBO', 'F-150 / LOBO', 2024, 2026),
    (32, 'CHEVROLET', 'SILVEADO', 'SILVERADO', 1992, 1994),
)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def catalog_state(cursor):
    result = {}
    for table in TABLES:
        cursor.execute(f'SELECT * FROM "{table}" ORDER BY id')
        result[table] = {'columns': [column[0] for column in cursor.description],
                         'rows': cursor.fetchall()}
    return result


def state_hash(state):
    def canonical(value):
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(timezone.utc).isoformat()
        return str(value)
    return hashlib.sha256(json.dumps(state, default=canonical, sort_keys=True).encode()).hexdigest()


def database_identity():
    config = connection.settings_dict
    return hashlib.sha256(json.dumps({k: config[k] for k in ('HOST', 'PORT', 'NAME')}, sort_keys=True).encode()).hexdigest()


def pending_changes(models):
    by_id = {model.pk: model for model in models}
    changes = []
    for pk, brand, old, new, start, end in PLAN:
        model = by_id.get(pk)
        if model is None or (model.marca.nombre, model.anio_inicio, model.anio_fin) != (brand, start, end):
            raise CommandError(f'El modelo {pk} no coincide con la marca y los anios aprobados.')
        if model.nombre not in (old, new):
            raise CommandError(f'El nombre del modelo {pk} cambio desde la auditoria. No se modifica nada.')
        if any(other.pk != pk and other.marca_id == model.marca_id
               and other.nombre.strip().upper() == new.upper()
               and (other.anio_inicio, other.anio_fin) == (start, end) for other in models):
            raise CommandError(f'Conflicto de nombre destino en modelo {pk}.')
        if model.nombre == old:
            changes.append((model, old, new))
    return changes
