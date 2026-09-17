from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
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


@admin_required
def producto_list(request):
	objects = Producto.objects.select_related('modelo', 'modelo__marca', 'categoria')
	search = request.GET.get('q', '').strip()
	marca_id = request.GET.get('marca', '').strip()
	modelo_id = request.GET.get('modelo', '').strip()
	categoria_id = request.GET.get('categoria', '').strip()
	anio = request.GET.get('anio', '').strip()
	activo = request.GET.get('activo', '').strip()

	if search:
		objects = objects.filter(
			Q(sku__icontains=search)
			| Q(nombre_pieza__icontains=search)
			| Q(modelo__nombre__icontains=search)
			| Q(modelo__marca__nombre__icontains=search)
			| Q(categoria__nombre__icontains=search)
		)
	if marca_id.isdigit():
		objects = objects.filter(modelo__marca_id=marca_id)
	if modelo_id.isdigit():
		objects = objects.filter(modelo_id=modelo_id)
	if categoria_id.isdigit():
		objects = objects.filter(categoria_id=categoria_id)
	if anio.isdigit():
		objects = objects.filter(anio_inicio__lte=anio, anio_fin__gte=anio)
	if activo in ('1', '0'):
		objects = objects.filter(activo=activo == '1')

	objects = objects.order_by('modelo__marca__nombre', 'modelo__nombre', 'anio_inicio', 'nombre_pieza')
	return render(request, 'catalogo/producto_list.html', {
		'objects': objects,
		'title': 'Productos',
		'marcas': Marca.objects.order_by('nombre'),
		'modelos': ModeloVehiculo.objects.select_related('marca').order_by('marca__nombre', 'nombre', 'anio_inicio'),
		'categorias': Categoria.objects.order_by('nombre'),
		'filters': {
			'q': search, 'marca': marca_id, 'modelo': modelo_id,
			'categoria': categoria_id, 'anio': anio, 'activo': activo,
		},
	})


def vehicle_selector(request, marca_id=None, modelo_id=None, anio=None):
	marca = get_object_or_404(Marca, pk=marca_id, activo=True) if marca_id else None
	modelo = get_object_or_404(ModeloVehiculo, pk=modelo_id, marca=marca, activo=True) if modelo_id else None

	context = {
		'title': 'Encuentra tu repuesto',
		'marca': marca,
		'modelo': modelo,
		'selected_year': anio,
	}

	if not marca:
		context['options'] = Marca.objects.filter(activo=True, modelos__activo=True).distinct().order_by('nombre')
		context['step'] = 'brand'
	elif not modelo:
		context['options'] = marca.modelos.filter(activo=True).order_by('nombre', 'anio_inicio', 'anio_fin')
		context['step'] = 'model'
	else:
		years = set()
		for product in Producto.objects.filter(modelo=modelo, activo=True).only('anio_inicio', 'anio_fin'):
			years.update(range(product.anio_inicio, product.anio_fin + 1))
		if anio is None:
			context['options'] = sorted(years, reverse=True)
			context['step'] = 'year'
		else:
			context['step'] = 'results'
			context['products'] = Producto.objects.filter(
				modelo=modelo,
				activo=True,
				anio_inicio__lte=anio,
				anio_fin__gte=anio,
			).select_related('categoria').order_by('nombre_pieza')

	return render(request, 'catalogo/vehicle_selector.html', context)
