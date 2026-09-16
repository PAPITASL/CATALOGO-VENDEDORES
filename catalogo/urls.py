from django.urls import path

from . import views

app_name = 'catalogo'

urlpatterns = [
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
