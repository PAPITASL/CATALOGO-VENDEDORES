from django.contrib import admin

from .models import Categoria, Marca, ModeloVehiculo, Producto


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo', 'fecha_creacion')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(ModeloVehiculo)
class ModeloVehiculoAdmin(admin.ModelAdmin):
    list_display = ('marca', 'nombre', 'activo')
    list_filter = ('activo', 'marca')
    search_fields = ('nombre', 'marca__nombre')


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nombre_pieza', 'modelo__marca', 'modelo', 'precio_venta', 'activo')
    list_filter = ('activo', 'modelo__marca', 'categoria')
    search_fields = ('sku', 'nombre_pieza', 'modelo__marca__nombre', 'modelo__nombre')
    ordering = ('modelo__marca__nombre', 'modelo__nombre', 'anio_inicio')
