from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_STORED

from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .clean_images import clean_filename, process_next_image
from .models import CatalogImageJob, CatalogImageItem
from .views import admin_required, filtered_products


@admin_required
@require_http_methods(['GET', 'POST'])
def start(request, with_heading=False):
    products, filters = filtered_products(request.GET)
    count = products.count()
    error = ''
    if request.method == 'POST':
        if not count:
            error = 'No hay productos que coincidan con estos filtros.'
        else:
            with transaction.atomic():
                # Serialize double-clicks and simultaneous tabs for this user.
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                job = CatalogImageJob.objects.filter(owner=request.user, active=True).first()
                if job is not None and job.with_heading != with_heading:
                    return render(request, 'catalogo/clean_image_start.html', {
                        'count': count, 'with_heading': with_heading, 'active_job': job,
                        'error': 'Termina la generación en curso antes de iniciar este tipo de imágenes.',
                    })
                if job is None:
                    job = CatalogImageJob.objects.create(owner=request.user, filters=filters, with_heading=with_heading)
                    batch = []
                    names = set()
                    for product in products.iterator(chunk_size=100):
                        name = clean_filename(product)
                        if name.casefold() in names:
                            name = f'{name[:-4]}_ID_{product.pk}.jpg'
                        while name.casefold() in names:
                            name = name[:-4] + '_.jpg'
                        names.add(name.casefold())
                        batch.append(CatalogImageItem(
                            heading={'piece': product.nombre_pieza,
                                     'vehicle': (f'{product.modelo.marca.nombre} · {product.modelo.nombre} · '
                                                 f'{product.anio_inicio}-{product.anio_fin}')} if with_heading else {},
                            job=job, product=product, source=product.imagen_principal.name or '',
                            filename=name, description=f'{product.nombre_pieza} — {product.modelo}',
                        ))
                        if len(batch) == 100:
                            CatalogImageItem.objects.bulk_create(batch)
                            batch = []
                    CatalogImageItem.objects.bulk_create(batch)
            return redirect('catalogo:clean_image_job', job_id=job.pk)
    return render(request, 'catalogo/clean_image_start.html', {
        'count': count, 'error': error, 'with_heading': with_heading,
        'jobs': CatalogImageJob.objects.filter(owner=request.user, with_heading=with_heading).order_by('-created_at')[:10],
    })


def owned_job(request, job_id):
    return get_object_or_404(CatalogImageJob, pk=job_id, owner=request.user)


@admin_required
@require_http_methods(['POST'])
def process(request, job_id):
    job = owned_job(request, job_id)
    if job.active:
        process_next_image(job.pk)
    return JsonResponse({'ok': True})


@admin_required
@require_GET
def detail(request, job_id):
    job = owned_job(request, job_id)
    total = job.items.count()
    successful = job.items.filter(status='done').count()
    failed = job.items.filter(status='error').count()
    summary = {'total': total, 'successful': successful, 'failed': failed,
               'processed': successful + failed, 'active': job.active}
    if request.GET.get('status') == '1':
        return JsonResponse(summary)
    from django.core.paginator import Paginator
    return render(request, 'catalogo/clean_image_job.html', {
        'job': job, 'summary': summary,
        'items': Paginator(job.items.order_by('pk'), 25).get_page(request.GET.get('page')),
    })


@admin_required
@require_GET
def image_download(request, job_id, item_id):
    job = owned_job(request, job_id)
    item = get_object_or_404(job.items, pk=item_id, status='done')
    try:
        source = item.image.open('rb')
    except FileNotFoundError:
        raise Http404('Imagen no disponible')
    return FileResponse(source, as_attachment=True, filename=item.filename, content_type='image/jpeg')


@admin_required
@require_GET
def zip_download(request, job_id):
    job = owned_job(request, job_id)
    if job.active:
        return JsonResponse({'error': 'El catálogo aún se está generando.'}, status=409)
    archive = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    errors = []
    try:
        with ZipFile(archive, 'w', ZIP_STORED, allowZip64=True) as output:
            for item in job.items.order_by('pk').iterator(chunk_size=100):
                if item.status != 'done':
                    errors.append(f'{item.filename}: {item.error}')
                    continue
                try:
                    with item.image.open('rb') as source:
                        output.writestr(item.filename, source.read())
                except OSError:
                    errors.append(f'{item.filename}: archivo no disponible')
            if errors:
                output.writestr('errores.txt', '\n'.join(errors))
        archive.seek(0)
        return FileResponse(archive, as_attachment=True, filename=f'IMAGENES_CATALOGO_{job.pk}.zip', content_type='application/zip')
    except BaseException:
        archive.close()
        raise
