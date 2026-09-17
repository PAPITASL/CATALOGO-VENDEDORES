from django.urls import path

from . import views

app_name = 'catalogo'

urlpatterns = [
    path('', views.vehicle_selector, name='vehicle_selector'),
    path('seleccionar/', views.vehicle_selector, name='vehicle_selector_start'),
    path('seleccionar/marca/<int:marca_id>/', views.vehicle_selector, name='vehicle_selector_model'),
    path('seleccionar/marca/<int:marca_id>/modelo/<int:modelo_id>/', views.vehicle_selector, name='vehicle_selector_year'),
    path('seleccionar/marca/<int:marca_id>/modelo/<int:modelo_id>/anio/<int:anio>/', views.vehicle_selector, name='vehicle_selector_products'),
    path('marcas/', views.marca_list, name='marca_list'),
    path('marcas/nueva/', views.marca_create, name='marca_create'),
    path('marcas/<int:pk>/editar/', views.marca_update, name='marca_update'),
    path('marcas/<int:pk>/eliminar/', views.marca_delete, name='marca_delete'),
    path('modelos/', views.modelo_list, name='modelovehiculo_list'),
    path('modelos/nuevo/', views.modelo_create, name='modelovehiculo_create'),
    path('modelos/<int:pk>/editar/', views.modelo_update, name='modelovehiculo_update'),
    path('modelos/<int:pk>/eliminar/', views.modelo_delete, name='modelovehiculo_delete'),
    path('categorias/', views.categoria_list, name='categoria_list'),
    path('categorias/nueva/', views.categoria_create, name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.categoria_update, name='categoria_update'),
    path('categorias/<int:pk>/eliminar/', views.categoria_delete, name='categoria_delete'),
    path('productos/', views.producto_list, name='producto_list'),
    path('productos/nuevo/', views.producto_create, name='producto_create'),
    path('productos/<int:pk>/editar/', views.producto_update, name='producto_update'),
    path('productos/<int:pk>/eliminar/', views.producto_delete, name='producto_delete'),
]
