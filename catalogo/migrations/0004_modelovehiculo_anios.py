from django.db import migrations, models
from django.db.models import F, Q


def completar_anios_desde_productos(apps, schema_editor):
    ModeloVehiculo = apps.get_model('catalogo', 'ModeloVehiculo')
    Producto = apps.get_model('catalogo', 'Producto')
    for modelo in ModeloVehiculo.objects.all():
        productos = Producto.objects.filter(modelo_id=modelo.pk)
        inicios = productos.values_list('anio_inicio', flat=True)
        finales = productos.values_list('anio_fin', flat=True)
        if productos.exists():
            modelo.anio_inicio = min(inicios)
            modelo.anio_fin = max(finales)
            modelo.save(update_fields=['anio_inicio', 'anio_fin'])


class Migration(migrations.Migration):
    dependencies = [('catalogo', '0003_alter_producto_imagen_principal')]

    operations = [
        migrations.RemoveConstraint(model_name='modelovehiculo', name='uq_modelo_marca'),
        migrations.AddField(
            model_name='modelovehiculo', name='anio_inicio',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='modelovehiculo', name='anio_fin',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(completar_anios_desde_productos, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='modelovehiculo',
            constraint=models.UniqueConstraint(
                fields=('marca', 'nombre', 'anio_inicio', 'anio_fin'),
                name='uq_modelo_marca_anios',
            ),
        ),
        migrations.AddConstraint(
            model_name='modelovehiculo',
            constraint=models.CheckConstraint(
                condition=Q(anio_inicio__isnull=True) | Q(anio_fin__isnull=True) | Q(anio_fin__gte=F('anio_inicio')),
                name='chk_anios_modelo',
            ),
        ),
    ]
