"""Full PostgreSQL and media backup, with an isolated restoration exercise."""
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from catalogo.vehicle_safety import catalog_state, database_identity, file_hash, state_hash


class Command(BaseCommand):
    help = 'Respalda PostgreSQL y media; verifica restauracion en una base nueva aislada.'

    def add_arguments(self, parser):
        parser.add_argument('--pg-bin', required=True)
        parser.add_argument('--output-dir', default='.vehicle-audit')

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Requiere PostgreSQL.')
        pg_bin = Path(options['pg_bin'])
        executables = [pg_bin / name for name in ('pg_dump.exe', 'pg_restore.exe')]
        if not all(path.is_file() for path in executables):
            raise CommandError('No se encuentran pg_dump.exe y pg_restore.exe.')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
        root = Path(options['output_dir']).resolve() / f'backup-{stamp}'
        root.mkdir(parents=True, exist_ok=False)
        config = connection.settings_dict
        env = os.environ.copy()
        for key, field in [('PGHOST', 'HOST'), ('PGPORT', 'PORT'), ('PGUSER', 'USER'),
                           ('PGPASSWORD', 'PASSWORD'), ('PGDATABASE', 'NAME')]:
            env[key] = str(config[field])
        dump = root / 'database.dump'

        def run(arguments):
            process = subprocess.run([str(arg) for arg in arguments], env=env, capture_output=True)
            if process.returncode:
                # Do not echo connection strings, environment variables or backup contents.
                (root / 'tool-error.log').write_bytes(process.stderr)
                raise CommandError(f'Fallo una herramienta PostgreSQL. Ver {root / "tool-error.log"}. No aplicar cambios.')

        run([executables[0], '--no-password', '--format=custom', '--no-owner', '--no-privileges', '--file', dump])
        self.stdout.write('Backup PostgreSQL creado. Verificando media y restauracion aislada...')
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.is_dir():
            raise CommandError('No existe MEDIA_ROOT. No se puede verificar el respaldo de imagenes.')
        media_path = root / 'media.zip'
        files = sorted(path for path in media_root.rglob('*') if path.is_file())
        media_hashes = {}
        with zipfile.ZipFile(media_path, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for path in files:
                relative = path.relative_to(media_root).as_posix()
                media_hashes[relative] = file_hash(path)
                archive.write(path, relative)
        with zipfile.ZipFile(media_path) as archive:
            if set(archive.namelist()) != set(media_hashes):
                raise CommandError('El archivo media no coincide con la lista original.')
            import hashlib
            for relative, expected in media_hashes.items():
                digest = hashlib.sha256()
                with archive.open(relative) as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                if digest.hexdigest() != expected or file_hash(media_root / relative) != expected:
                    raise CommandError('El respaldo de media cambio o no coincide.')
        current_files = {path.relative_to(media_root).as_posix() for path in media_root.rglob('*') if path.is_file()}
        if current_files != set(media_hashes):
            raise CommandError('La lista de media cambio durante el respaldo.')
        # Never overwrite, clean or drop an existing database.
        scratch = f'vehicle_restore_{stamp}'
        connection.ensure_connection()
        if not connection.get_autocommit():
            raise CommandError('La verificacion requiere autocommit para crear una base aislada.')
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE DATABASE "{scratch}" TEMPLATE template0')
        run([executables[1], '--no-password', '--exit-on-error', '--no-owner', '--no-privileges', '--dbname', scratch, dump])
        params = connection.get_connection_params()
        params['dbname'] = scratch
        with connection.Database.connect(**params) as restored:
            with restored.cursor() as cursor:
                # Django's psycopg context decodes timestamps using its configured
                # timezone; initialize the raw connection to that same timezone.
                cursor.execute("SELECT set_config('TimeZone', %s, false)", [connection.timezone_name])
                restored_hash = state_hash(catalog_state(cursor))
        with connection.cursor() as cursor:
            current_hash = state_hash(catalog_state(cursor))
        if restored_hash != current_hash:
            raise CommandError('El catalogo cambio desde pg_dump o la restauracion no coincide. No aplicar cambios.')
        manifest = {
            'verified': True, 'database_identity': database_identity(), 'catalog_sha256': current_hash,
            'dump_sha256': file_hash(dump), 'media_zip_sha256': file_hash(media_path),
            'media_files': media_hashes, 'restore_database': scratch,
            'restore_test': 'pg_restore --exit-on-error completed; catalog rows match source',
            'scope': 'Full database schema/data without roles/ownership/privileges; full local MEDIA_ROOT files',
        }
        (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Respaldo verificado: {root}; imagenes: {len(files)}. Base de ensayo conservada: {scratch}'))
