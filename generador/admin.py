from django.contrib import admin

from .models import Plantilla


@admin.register(Plantilla)
class PlantillaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ancho', 'alto', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)
