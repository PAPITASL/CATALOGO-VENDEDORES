import base64
import mimetypes
from html import escape
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.safestring import mark_safe
import resvg

from catalogo.models import Producto

from .forms import GenerarImagenForm


def _money(value):
	return f'${value:,.0f}'.replace(',', '.')


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
	logo_path = settings.MEDIA_ROOT / 'logo_lujoshop.png'
	if not logo_path.exists():
		return None
	try:
		encoded = base64.b64encode(logo_path.read_bytes()).decode('ascii')
	except OSError:
		return None
	return f'data:image/png;base64,{encoded}'


def build_product_svg(producto, precio):
	image_href = _image_data_uri(producto)
	logo_href = _logo_data_uri()
	image_element = (
		f'<image href="{image_href}" x="24" y="24" width="902" height="852" preserveAspectRatio="xMidYMid meet"/>'
		if image_href
		else '<text x="475" y="450" text-anchor="middle" class="missing">Sin fotografía</text>'
	)
	logo_element = (
		f'<image href="{logo_href}" x="1000" y="20" width="190" height="42" preserveAspectRatio="xMinYMid meet"/>'
		if logo_href
		else '<text x="1000" y="48" class="logo-fallback">LUJOSHOP</text>'
	)
	marca = escape(producto.modelo.marca.nombre)
	modelo = escape(producto.modelo.nombre)
	pieza = escape(producto.nombre_pieza)
	observaciones = escape(producto.observaciones or 'Sin observaciones')
	years = f'{producto.anio_inicio} - {producto.anio_fin}'
	return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
	  <rect width="1600" height="900" fill="#ffffff"/>
	  <rect x="950" width="650" height="900" fill="#ffffff"/>
	  <line x1="950" y1="0" x2="950" y2="900" class="divider"/>
  {image_element}
	  {logo_element}
	  <text x="1210" y="48" class="eyebrow">CATALOGO</text>
	  <text x="1000" y="160" class="brand">{marca}</text>
	  <text x="1000" y="220" class="model">{modelo}</text>
	  <line x1="1000" y1="260" x2="1540" y2="260" class="line"/>
	  <text x="1000" y="335" class="label">COMPATIBILIDAD</text>
	  <text x="1000" y="385" class="value">{years}</text>
	  <text x="1000" y="475" class="label">PIEZA</text>
	  <text x="1000" y="525" class="piece">{pieza}</text>
	  <text x="1000" y="625" class="label">PRECIO MINIMO</text>
	  <text x="1000" y="680" class="minimum">{_money(producto.precio_minimo)}</text>
	  <text x="1000" y="745" class="label">PRECIO DE PUBLICACION</text>
	  <text x="1000" y="815" class="price">{_money(precio)}</text>
	  <text x="1000" y="855" class="note">{observaciones}</text>
	  <text x="1000" y="885" class="sku">SKU {escape(producto.sku or 'SIN SKU')}</text>
  <style>
	.eyebrow,.label,.sku {{ font-family: sans-serif; letter-spacing: 3px; }}
	.eyebrow {{ fill: #a15d38; font-size: 18px; font-weight: 700; }}
	.logo-fallback {{ fill: #1e2827; font: 700 24px sans-serif; letter-spacing: 3px; }}
	.label {{ fill: #7a746c; font-size: 16px; font-weight: 700; }}
	.brand {{ fill: #1e2827; font: 700 58px sans-serif; }}
	.model {{ fill: #1e2827; font: 400 42px sans-serif; }}
	.value {{ fill: #1e2827; font: 400 38px sans-serif; }}
	.piece {{ fill: #1e2827; font: 700 34px sans-serif; }}
	.price {{ fill: #a15d38; font: 700 66px sans-serif; }}
	.minimum {{ fill: #1e2827; font: 400 34px sans-serif; }}
	.note {{ fill: #4d514d; font: 400 24px sans-serif; }}
	.sku {{ fill: #7a746c; font-size: 14px; }}
	.line {{ stroke: #c8b9a8; stroke-width: 2; }}
	.divider {{ stroke: #ddd8d0; stroke-width: 2; }}
	.missing {{ fill: #9b938a; font: 700 24px sans-serif; }}
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
	filename = f'{Path(producto.sku or producto.nombre_pieza).stem}.svg'
	response = HttpResponse(svg, content_type='image/svg+xml; charset=utf-8')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


@login_required
def download_product_png(request, pk):
	producto = get_object_or_404(Producto.objects.select_related('modelo__marca'), pk=pk, activo=True)
	form = GenerarImagenForm(request.GET or None, producto=producto)
	if not form.is_valid():
		return HttpResponse('Precio de publicación inválido.', status=400)
	svg = build_product_svg(producto, form.cleaned_data['precio_publicacion'])
	tree = resvg.usvg.Tree.from_str(svg, resvg.usvg.Options.default())
	png = resvg.render(tree, (1, 0, 0, 1, 0, 0))
	filename = f'{Path(producto.sku or producto.nombre_pieza).stem}.png'
	response = HttpResponse(png, content_type='image/png')
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response
