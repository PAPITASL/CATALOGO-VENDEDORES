"""Independent photo editing pipeline; does not use publication downloads."""
import logging
import re
from datetime import timedelta
from io import BytesIO
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont, ImageOps

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


def heading_lines(draw, text, font, width=752):
    """Wrap by measured pixels, including identifiers without spaces."""
    lines = []
    line = ''
    for word in str(text).split():
        candidate = f'{line} {word}' if line else word
        if draw.textlength(candidate, font=font) <= width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = ''
        for char in word:
            if line and draw.textlength(line + char, font=font) > width:
                lines.append(line)
                line = ''
            line += char
    if line:
        lines.append(line)
    return lines


def compose_heading_jpeg(raw, heading):
    """Keep the full photograph below a fitted heading on an 800 x 600 JPG."""
    canvas = Image.new('RGB', (800, 600), 'white')
    draw = ImageDraw.Draw(canvas)
    for size in range(30, 11, -1):
        title_font = ImageFont.load_default(size=size)
        vehicle_font = ImageFont.load_default(size=size - 3)
        title = heading_lines(draw, heading['piece'], title_font)
        vehicle = heading_lines(draw, heading['vehicle'], vehicle_font)
        header_height = 36 + len(title) * (size + 8) + len(vehicle) * (size + 5)
        if header_height <= 220:
            break
    y = 16
    for lines, font, step, color in (
        (title, title_font, size + 8, '#172435'),
        (vehicle, vehicle_font, size + 5, '#46566a'),
    ):
        for line in lines:
            draw.text((400, y), line, font=font, fill=color, anchor='mt')
            y += step
    draw.line((24, header_height - 8, 776, header_height - 8), fill='#dce2e8', width=2)
    with Image.open(BytesIO(raw)) as original:
        photo = ImageOps.exif_transpose(original).convert('RGBA')
        photo = ImageOps.contain(photo, (800, 600 - header_height), Image.Resampling.LANCZOS)
        canvas.paste(photo, ((800 - photo.width) // 2,
                            header_height + (600 - header_height - photo.height) // 2), photo)
    output = BytesIO()
    canvas.save(output, 'JPEG', quality=95, subsampling=0)
    return output.getvalue()


def resize_heading_photo(source, heading):
    if not source:
        raise FileNotFoundError('No original image')
    with default_storage.open(source, 'rb') as original:
        return compose_heading_jpeg(original.read(), heading)


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
        data = (resize_heading_photo(item.source, item.heading)
                if item.job.with_heading else resize_photo(item.source))
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
