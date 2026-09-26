"""Independent photo editing pipeline; does not use publication downloads."""
import logging
import re
from datetime import timedelta
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageOps

from .models import CatalogImageItem, CatalogImageJob

logger = logging.getLogger(__name__)


def clean_filename(product):
    name = f'{product.modelo.marca.nombre}_{product.modelo.nombre}_{product.anio_inicio}-{product.anio_fin}_{product.nombre_pieza}'
    name = re.sub(r'[\s<>:"/\\|?*\x00-\x1f\x7f]+', '_', name.upper())
    name = re.sub('_+', '_', name).strip('._')
    return name.encode('utf-8')[:190].decode('utf-8', errors='ignore') + '.jpg'


def resize_photo(source):
    if not source:
        raise FileNotFoundError('No original image')
    with default_storage.open(source, 'rb') as original:
        return compose_jpeg(original.read())


def compose_jpeg(raw):
    with Image.open(BytesIO(raw)) as image:
        # Honor camera orientation, keep the entire photo, and never crop.
        image = ImageOps.exif_transpose(image).convert('RGBA')
        image = ImageOps.contain(image, (800, 600), Image.Resampling.LANCZOS)
        canvas = Image.new('RGB', (800, 600), 'white')
        canvas.paste(image, ((800 - image.width) // 2, (600 - image.height) // 2), image)
        output = BytesIO()
        canvas.save(output, 'JPEG', quality=95, subsampling=0)
        return output.getvalue()


def process_next_image(job_id=None):
    # Recover interrupted jobs without touching their source files.
    CatalogImageItem.objects.filter(status='processing', updated_at__lt=timezone.now() - timedelta(minutes=10)).update(
        status='error', error='Proceso interrumpido. Revisa el resultado antes de generar nuevamente.')
    for job in CatalogImageJob.objects.filter(active=True).iterator():
        if not job.items.filter(status__in=['pending', 'processing']).exists():
            CatalogImageJob.objects.filter(pk=job.pk).update(active=False)
    pending = CatalogImageItem.objects.filter(status='pending', job__active=True)
    if job_id is not None:
        pending = pending.filter(job_id=job_id)
    item = pending.order_by('pk').first()
    if item is None:
        return False
    if not CatalogImageItem.objects.filter(pk=item.pk, status='pending').update(status='processing', updated_at=timezone.now()):
        return True
    stored_name = None
    try:
        data = resize_photo(item.source)
        path = str(PurePosixPath('catalogo_limpio', str(item.job_id), str(item.pk), item.filename))
        stored_name = default_storage.save(path, ContentFile(data))
        item.image.name = stored_name
        item.status = 'done'
    except Exception as exc:
        logger.error('Catalog image item %s failed (%s)', item.pk, type(exc).__name__)
        item.status = 'error'
        item.error = 'Falta la imagen original o no se puede leer.' if isinstance(exc, (FileNotFoundError, OSError)) else 'No se pudo ajustar o guardar la imagen.'
    item.save(update_fields=['image', 'status', 'error', 'updated_at'])
    if not item.job.items.filter(status__in=['pending', 'processing']).exists():
        CatalogImageJob.objects.filter(pk=item.job_id).update(active=False)
    return True
