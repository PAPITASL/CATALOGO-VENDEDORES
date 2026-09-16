from django.urls import path

from . import views

app_name = 'generador'

urlpatterns = [
    path('productos/<int:pk>/', views.product_generator, name='product_generator'),
    path('productos/<int:pk>/descargar/', views.download_product_svg, name='download_product_svg'),
    path('productos/<int:pk>/descargar-png/', views.download_product_png, name='download_product_png'),
]
