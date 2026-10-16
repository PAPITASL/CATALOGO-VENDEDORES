import base64
import mimetypes
import re
import unicodedata

from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
from django.utils.http import content_disposition_header
import resvg

from catalogo.models import Producto

from .forms import GenerarImagenForm
from .layout import TextFlow
from .branding import Branding, RED, BLACK, GRAY, SILVER


def _money(value):
	return f'${value:,.0f}'.replace(',', '.')


def product_download_filename(producto, extension):
	parts = (
		producto.modelo.marca.nombre, producto.modelo.nombre,
		str(producto.anio_inicio), str(producto.anio_fin), producto.nombre_pieza,
	)
	name = unicodedata.normalize('NFC', '_'.join(parts)).upper()
	# Remove characters forbidden in Windows filenames and normalize separators.
	name = re.sub(r'[\s<>:"/\\|?*\x00-\x1f\x7f]+', '_', name)
	name = re.sub(r'_+', '_', name).strip('._')
	return f'{name}.{extension}'


def _image_data_uri(producto):
	if not producto.imagen_principal:
		return None
	try:
		with default_storage.open(producto.imagen_principal.name, 'rb') as image_file:
			encoded = base64.b64encode(image_file.read()).decode('ascii')
	except (FileNotFoundError, OSError):
		return None
	content_type = mimetypes.guess_type(producto.imagen_principal.name)[0] or 'image/jpeg'
	return f'data:{content_type};base64,{encoded}'


def _logo_data_uri():
	return Branding(1600, 900, max_height=70).data_uri()


def build_product_svg(producto, precio):
	branding = Branding(1600, 900, max_height=70)
	flow = TextFlow()
	flow.text(producto.modelo.marca.nombre, 'brand', 48, gap=8)
	flow.text(producto.modelo.nombre, 'model', 36, gap=20)
	flow.elements.append(f'<line x1="1000" y1="{flow.y}" x2="1540" y2="{flow.y}" class="line"/>')
	flow.y += 24
	flow.field('COMPATIBILIDAD', f'{producto.anio_inicio} - {producto.anio_fin}', 'value', 32)
	flow.field('PIEZA', producto.nombre_pieza, 'piece', 30)
	flow.field('PRECIO MINIMO', _money(producto.precio_minimo), 'minimum', 30)
	flow.field('PRECIO DE PUBLICACION', _money(precio), 'price', 48)
	flow.text(producto.observaciones or 'Sin observaciones', 'note', 22, gap=18)
	flow.text(f"SKU {producto.sku or 'SIN SKU'}", 'sku', 14, gap=0)
	height = max(900, flow.y + 30)
	text_elements = '\n'.join(flow.elements)
	image_href = _image_data_uri(producto)
	logo_href = _logo_data_uri()
	image_element = (
		f'<image href="{image_href}" x="24" y="24" width="902" height="{height - 48}" preserveAspectRatio="xMidYMid meet"/>'
		if image_href
		else f'<text x="475" y="{height // 2}" text-anchor="middle" class="missing">Sin fotografía</text>'
	)
	logo_element = branding.svg(logo_href)
	return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" viewBox="0 0 1600 {height}">
	  <rect width="1600" height="{height}" fill="#ffffff"/>
	  <rect x="950" width="650" height="{height}" fill="#ffffff"/>
	  <line x1="950" y1="0" x2="950" y2="{height}" class="divider"/>
  {image_element}
	  {logo_element}
	  <text x="1000" y="48" class="eyebrow">CATALOGO</text>
	  {text_elements}
  <style>
	.eyebrow,.label {{ font-family: sans-serif; letter-spacing: 3px; }}
	.eyebrow {{ fill: {RED}; font-size: 18px; font-weight: 700; }}
	.label {{ fill: {GRAY}; font-size: 16px; font-weight: 700; }}
	.brand {{ fill: {BLACK}; font: 700 48px sans-serif; }}
	.model {{ fill: {BLACK}; font: 400 36px sans-serif; }}
	.value {{ fill: {BLACK}; font: 400 32px sans-serif; }}
	.piece {{ fill: {BLACK}; font: 700 30px sans-serif; }}
	.price {{ fill: {RED}; font: 700 48px sans-serif; }}
	.minimum {{ fill: {RED}; font: 400 30px sans-serif; }}
	.note {{ fill: {GRAY}; font: 400 22px sans-serif; }}
	.sku {{ fill: {GRAY}; font: 400 14px sans-serif; }}
	.line {{ stroke: {RED}; stroke-width: 2; }}
	.divider {{ stroke: {SILVER}; stroke-width: 2; }}
	.missing {{ fill: {GRAY}; font: 700 24px sans-serif; }}
  </style>
</svg>'''


@login_required
def product_generator(request, pk):
	producto = get_object_or_404(Producto.objects.select_related('modelo__marca', 'categoria'), pk=pk, activo=True)
	form = GenerarImagenForm(request.POST or None, producto=producto)
	svg = None
	if request.method == 'POST' and form.is_valid():
		svg = build_product_svg(producto, form.cleaned_data['precio_publicacion'])
	return render(request, 'generador/product_generator.html', {
		'producto': producto,
		'form': form,
		'svg_preview': mark_safe(svg) if svg else None,
	})


@login_required
def download_product_svg(request, pk):
	producto = get_object_or_404(Producto.objects.select_related('modelo__marca'), pk=pk, activo=True)
	form = GenerarImagenForm(request.GET or None, producto=producto)
	if not form.is_valid():
		return HttpResponse('Precio de publicación inválido.', status=400)
	svg = build_product_svg(producto, form.cleaned_data['precio_publicacion'])
	filename = product_download_filename(producto, 'svg')
	response = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
	response['Content-Disposition'] = content_disposition_header(True, filename)
	return response


@login_required
def download_product_png(request, pk):
	producto = get_object_or_404(Producto.objects.select_related('modelo__marca'), pk=pk, activo=True)
	form = GenerarImagenForm(request.GET or None, producto=producto)
	if not form.is_valid():
		return HttpResponse('Precio de publicación inválido.', status=400)
	png = generate_product_png(producto, form.cleaned_data['precio_publicacion'])
	filename = product_download_filename(producto, 'png')
	response = HttpResponse(png, content_type='image/png')
	response['Content-Disposition'] = content_disposition_header(True, filename)
	return response


def generate_product_png(producto, precio):
	svg = build_product_svg(producto, precio)
	options = resvg.usvg.Options.default()
	options.load_system_fonts()
	tree = resvg.usvg.Tree.from_str(svg, options)
	# resvg expects row-major (a, b, tx, c, d, ty), not SVG matrix order.
	return bytes(resvg.render(tree, (1, 0, 0, 0, 1, 0)))
