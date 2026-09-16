from django.db import models


class Plantilla(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    archivo_svg = models.CharField(max_length=500)
    ancho = models.IntegerField()
    alto = models.IntegerField()
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'plantillas'
        verbose_name = 'Plantilla'
        verbose_name_plural = 'Plantillas'
        constraints = [
            models.CheckConstraint(condition=models.Q(ancho__gt=0), name='chk_ancho_plantilla'),
            models.CheckConstraint(condition=models.Q(alto__gt=0), name='chk_alto_plantilla'),
        ]

    def __str__(self):
        return self.nombre
