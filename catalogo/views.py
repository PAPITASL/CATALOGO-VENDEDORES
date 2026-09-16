from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoriaForm, MarcaForm, ModeloVehiculoForm, ProductoForm
from .models import Categoria, Marca, ModeloVehiculo, Producto


def admin_required(view_func):
	@wraps(view_func)
	@login_required
	def wrapped_view(request, *args, **kwargs):
		if not (request.user.is_staff or request.user.role == request.user.ROLE_ADMIN):
			raise PermissionDenied
		return view_func(request, *args, **kwargs)

	return wrapped_view


def _crud_views(model, form_class, template_name, title, success_message):
	@admin_required
	def list_view(request):
		objects = model.objects.all()
		return render(request, template_name, {'objects': objects, 'title': title})

	@admin_required
	def create_view(request):
		form = form_class(request.POST or None, request.FILES or None)
		if request.method == 'POST' and form.is_valid():
			form.save()
			messages.success(request, success_message)
			return redirect(f'catalogo:{model._meta.model_name}_list')
		return render(request, 'catalogo/form.html', {'form': form, 'title': f'Crear {title[:-1].lower()}'})

	@admin_required
	def update_view(request, pk):
		instance = get_object_or_404(model, pk=pk)
		form = form_class(request.POST or None, request.FILES or None, instance=instance)
		if request.method == 'POST' and form.is_valid():
			form.save()
			messages.success(request, success_message)
			return redirect(f'catalogo:{model._meta.model_name}_list')
		return render(request, 'catalogo/form.html', {'form': form, 'title': f'Editar {title[:-1].lower()}'})

	@admin_required
	def delete_view(request, pk):
		instance = get_object_or_404(model, pk=pk)
		if request.method == 'POST':
			instance.delete()
			messages.success(request, f'{title[:-1]} eliminado correctamente.')
			return redirect(f'catalogo:{model._meta.model_name}_list')
		return render(request, 'catalogo/confirm_delete.html', {'object': instance, 'title': f'Eliminar {title[:-1].lower()}'})

	return list_view, create_view, update_view, delete_view


marca_list, marca_create, marca_update, marca_delete = _crud_views(
	Marca, MarcaForm, 'catalogo/marca_list.html', 'Marcas', 'Marca guardada correctamente.'
)
modelo_list, modelo_create, modelo_update, modelo_delete = _crud_views(
	ModeloVehiculo, ModeloVehiculoForm, 'catalogo/modelo_list.html', 'Modelos', 'Modelo guardado correctamente.'
)
categoria_list, categoria_create, categoria_update, categoria_delete = _crud_views(
	Categoria, CategoriaForm, 'catalogo/categoria_list.html', 'Categorías', 'Categoría guardada correctamente.'
)
producto_list, producto_create, producto_update, producto_delete = _crud_views(
	Producto, ProductoForm, 'catalogo/producto_list.html', 'Productos', 'Producto guardado correctamente.'
)
