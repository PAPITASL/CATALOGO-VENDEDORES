import uuid

from django.conf import settings
from django.db import models


class CatalogImageJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    filters = models.JSONField(default=dict)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner'], condition=models.Q(active=True), name='one_active_image_job_per_user')]


class CatalogImageItem(models.Model):
    job = models.ForeignKey(CatalogImageJob, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalogo.Producto', null=True, on_delete=models.SET_NULL)
    source = models.CharField(max_length=500, blank=True)
    description = models.TextField()
    filename = models.CharField(max_length=250)
    status = models.CharField(max_length=16, default='pending', db_index=True)
    image = models.FileField(upload_to='catalogo_limpio/', max_length=500, blank=True)
    error = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
