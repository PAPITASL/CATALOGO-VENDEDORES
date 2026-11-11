from uuid import uuid4

from django.db import models, router, transaction
from django.db.models import F, Q
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    logo = models.CharField(max_length=500, blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'marcas'
        verbose_name = 'Marca'
        verbose_name_plural = 'Marcas'

    def __str__(self):
        return self.nombre


class ModeloVehiculo(models.Model):
    marca = models.ForeignKey(
        'Marca',
        on_delete=models.PROTECT,
        related_name='modelos',
        db_column='marca_id',
    )
    nombre = models.CharField(max_length=150)
    anio_inicio = models.IntegerField(blank=True, null=True)
    anio_fin = models.IntegerField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modelos_vehiculo'
        verbose_name = 'Modelo de vehículo'
        verbose_name_plural = 'Modelos de vehículos'
        constraints = [
            models.UniqueConstraint(fields=['marca', 'nombre', 'anio_inicio', 'anio_fin'], name='uq_modelo_marca_anios'),
            models.CheckConstraint(
                condition=Q(anio_inicio__isnull=True) | Q(anio_fin__isnull=True) | Q(anio_fin__gte=F('anio_inicio')),
                name='chk_anios_modelo',
            ),
        ]

    def __str__(self):
        years = f' ({self.anio_inicio}–{self.anio_fin})' if self.anio_inicio and self.anio_fin else ''
        return f'{self.marca} {self.nombre}{years}'


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'categorias'
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True)
    nombre_pieza = models.CharField(max_length=200)
    modelo = models.ForeignKey(
        'ModeloVehiculo',
        on_delete=models.PROTECT,
        related_name='productos',
        db_column='modelo_id',
    )
    categoria = models.ForeignKey(
        'Categoria',
        on_delete=models.SET_NULL,
        related_name='productos',
        db_column='categoria_id',
        blank=True,
        null=True,
    )
    anio_inicio = models.IntegerField()
    anio_fin = models.IntegerField()
    imagen_principal = models.FileField(upload_to='productos/', max_length=500)
    costo = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    precio_minimo = models.DecimalField(max_digits=12, decimal_places=2)
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'productos'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        constraints = [
            models.CheckConstraint(condition=Q(costo__isnull=True) | Q(costo__gte=0), name='chk_costo_positivo'),
            models.CheckConstraint(condition=Q(precio_minimo__gte=0), name='chk_precio_minimo'),
            models.CheckConstraint(condition=Q(precio_venta__gte=F('precio_minimo')), name='chk_precio_venta'),
            models.CheckConstraint(condition=Q(anio_fin__gte=F('anio_inicio')), name='chk_anios_producto'),
        ]

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            old_sku = None
            if not self._state.adding:
                old_sku = type(self).objects.using(using).filter(pk=self.pk).values_list('sku', flat=True).first()
            elif not self.sku:
                self.sku = str(_next_numeric_sku(using))

            super().save(*args, **kwargs)
            if old_sku != self.sku and _is_numeric_sku(old_sku):
                _renumber_numeric_skus(using)

    def __str__(self):
        return f'{self.modelo.marca} {self.modelo} - {self.nombre_pieza}'


def _is_numeric_sku(sku):
    return isinstance(sku, str) and sku.isascii() and sku.isdigit()


def _next_numeric_sku(using):
    numeric_skus = (
        sku for sku in Producto.objects.using(using).values_list('sku', flat=True)
        if _is_numeric_sku(sku)
    )
    return max((int(sku) for sku in numeric_skus), default=0) + 1


def _renumber_numeric_skus(using):
    manager = Producto.objects.using(using)
    products = [product for product in manager.only('pk', 'sku') if _is_numeric_sku(product.sku)]
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


@receiver(post_delete, sender=Producto)
def renumber_product_skus_after_delete(*, using, **_):
    _renumber_numeric_skus(using)


from .clean_models import CatalogImageJob, CatalogImageItem
