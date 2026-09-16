from django.db import models
from django.db.models import F, Q


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
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modelos_vehiculo'
        verbose_name = 'Modelo de vehículo'
        verbose_name_plural = 'Modelos de vehículos'
        constraints = [
            models.UniqueConstraint(fields=['marca', 'nombre'], name='uq_modelo_marca')
        ]

    def __str__(self):
        return f'{self.marca} {self.nombre}'


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

    def __str__(self):
        return f'{self.modelo.marca} {self.modelo} - {self.nombre_pieza}'
