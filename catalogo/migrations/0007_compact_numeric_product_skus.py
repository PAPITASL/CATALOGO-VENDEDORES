from uuid import uuid4

from django.db import migrations


def compact_numeric_product_skus(apps, schema_editor):
    Producto = apps.get_model('catalogo', 'Producto')
    using = schema_editor.connection.alias
    manager = Producto.objects.using(using)
    products = [
        product for product in manager.only('pk', 'sku')
        if isinstance(product.sku, str) and product.sku.isascii() and product.sku.isdigit()
    ]
    products.sort(key=lambda product: (int(product.sku), product.pk))
    if all(product.sku == str(number) for number, product in enumerate(products, start=1)):
        return

    prefix = f'__renumber_{uuid4().hex}_'
    while manager.filter(sku__startswith=prefix).exists():
        prefix = f'__renumber_{uuid4().hex}_'
    for product in products:
        product.sku = f'{prefix}{product.pk}'
    manager.bulk_update(products, ['sku'])

    for number, product in enumerate(products, start=1):
        product.sku = str(number)
    manager.bulk_update(products, ['sku'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalogo', '0006_catalogimageitem_heading_and_more'),
    ]

    operations = [
        migrations.RunPython(
            compact_numeric_product_skus,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
