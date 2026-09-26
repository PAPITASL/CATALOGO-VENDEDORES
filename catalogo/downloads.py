import logging
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_STORED

from generador.views import generate_product_png, product_download_filename

logger = logging.getLogger(__name__)


def build_catalog_zip(products):
    archive = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    used_names = set()
    errors = []
    first = None
    same_group = True
    count = 0
    try:
        # PNG is already compressed. Process one publication at a time.
        with ZipFile(archive, 'w', compression=ZIP_STORED, allowZip64=True) as zip_file:
            for product in products.iterator(chunk_size=100):
                group = (product.modelo_id, product.anio_inicio, product.anio_fin)
                if first is None:
                    first = product
                same_group = same_group and group == (first.modelo_id, first.anio_inicio, first.anio_fin)
                try:
                    png = generate_product_png(product, product.precio_venta)
                    stem = product_download_filename(product, 'png')[:-4]
                    # Leave room for suffixes and the extension on common filesystems.
                    stem = stem.encode('utf-8')[:200].decode('utf-8', errors='ignore').rstrip(' .')
                    name = f'{stem}.png'
                    suffix = 1
                    while name.casefold() in used_names:
                        name = f'{stem}_{suffix:02d}.png'
                        suffix += 1
                    zip_file.writestr(name, png)
                    used_names.add(name.casefold())
                    count += 1
                except Exception:
                    logger.exception('Error generating catalog publication for product %s', product.pk)
                    errors.append(f'SKU {product.sku or "SIN SKU"} - {product.nombre_pieza} (ID {product.pk})')
            if errors:
                zip_file.writestr('errores.txt', 'No fue posible generar:\n' + '\n'.join(errors))
        filename = 'CATALOGO_LUJOSHOP.zip'
        if first is not None and same_group:
            from types import SimpleNamespace
            group_product = SimpleNamespace(
                modelo=first.modelo, anio_inicio=first.anio_inicio, anio_fin=first.anio_fin,
                nombre_pieza='',
            )
            filename = product_download_filename(group_product, 'zip')
        archive.seek(0)
        return archive, filename, count
    except BaseException:
        archive.close()
        raise
