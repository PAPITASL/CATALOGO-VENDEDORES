from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, DecimalField, Q, Value, When
from django.db.models.functions import Cast, Lower
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET

from .forms import CategoriaForm, MarcaForm, ModeloVehiculoForm, ProductoForm
from .models import Categoria, Marca, ModeloVehiculo, Producto
from .downloads import build_catalog_zip


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
			try:
				instance.delete()
			except ProtectedError as error:
				protected = sorted(error.protected_objects, key=lambda obj: (obj._meta.label, obj.pk))
				return render(request, 'catalogo/confirm_delete.html', {
					'object': instance,
					'title': 'No se puede eliminar este registro',
					'blocked': True,
					'protected_count': len(protected),
					'protected_objects': [
						{'object': obj, 'edit_url': f'catalogo:{obj._meta.model_name}_update'}
						for obj in protected[:20]
					],
					'list_url': f'catalogo:{model._meta.model_name}_list',
				})
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


def filtered_products(params):
	objects = Producto.objects.select_related('modelo', 'modelo__marca', 'categoria')
	search = params.get('q', '').strip()
	marca_id = params.get('marca', '').strip()
	modelo_id = params.get('modelo', '').strip()
	categoria_id = params.get('categoria', '').strip()
	anio = params.get('anio', '').strip()
	activo = params.get('activo', '').strip()

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

	# Numeric SKUs must sort as 1, 2, 10; keep text codes and empty SKUs safe.
	objects = objects.annotate(
		sku_group=Case(
			When(sku__regex=r'^[0-9]+$', then=Value(0)),
			When(Q(sku__isnull=True) | Q(sku=''), then=Value(2)),
			default=Value(1),
		),
		sku_number=Case(
			When(sku__regex=r'^[0-9]+$', then=Cast('sku', DecimalField(max_digits=100, decimal_places=0))),
			default=None, output_field=DecimalField(max_digits=100, decimal_places=0),
		),
	).order_by('sku_group', 'sku_number', Lower('sku'), 'pk')
	return objects, {
		'q': search, 'marca': marca_id, 'modelo': modelo_id,
		'categoria': categoria_id, 'anio': anio, 'activo': activo,
	}


def catalog_download_products(params):
	objects, filters = filtered_products(params)
	if not any(filters.values()):
		objects = objects.filter(activo=True)
	return objects


@admin_required
def producto_list(request):
	objects, filters = filtered_products(request.GET)
	page = Paginator(objects, 25).get_page(request.GET.get('page'))
	query = request.GET.copy()
	query.pop('page', None)
	return render(request, 'catalogo/producto_list.html', {
		'objects': page,
		'page_obj': page,
		'pagination_query': query.urlencode(),
		'pagination_items': _pagination_items(page),
		'title': 'Productos',
		'marcas': Marca.objects.order_by('nombre'),
		'modelos': ModeloVehiculo.objects.select_related('marca').order_by('marca__nombre', 'nombre', 'anio_inicio'),
		'categorias': Categoria.objects.order_by('nombre'),
		'filters': filters,
		'download_count': catalog_download_products(request.GET).count(),
		'download_all': not any(filters.values()),
	})


def _pagination_items(page):
	# Keep five nearby pages at either end, using Django's elision for gaps.
	center = min(page.paginator.num_pages, max(3, min(page.number, page.paginator.num_pages - 2)))
	return [
		{'number': number, 'compact': isinstance(number, int) and (
			page.paginator.num_pages <= 4 or abs(number - page.number) <= 1
		)}
		for number in page.paginator.get_elided_page_range(center, on_each_side=2, on_ends=1)
	]


@admin_required
@require_GET
def download_catalog(request):
	products = catalog_download_products(request.GET)
	if not products.exists():
		return JsonResponse({'error': 'No hay productos para descargar con estos filtros.'}, status=400)
	archive, filename, count = build_catalog_zip(products)
	if not count:
		archive.close()
		return JsonResponse({'error': 'No se pudo generar ninguna publicación. Intenta nuevamente.'}, status=500)
	response = FileResponse(archive, as_attachment=True, filename=filename, content_type='application/zip')
	response['Cache-Control'] = 'no-store'
	return response


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
