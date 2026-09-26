from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .forms import ProductoForm
from .models import Categoria, Marca, ModeloVehiculo, Producto


class VehicleSelectorTests(TestCase):
	def setUp(self):
		self.marca = Marca.objects.create(nombre='Mazda')
		self.modelo = ModeloVehiculo.objects.create(
			marca=self.marca, nombre='CX-5', anio_inicio=2020, anio_fin=2022,
		)
		self.producto = Producto.objects.create(
			nombre_pieza='Farola', modelo=self.modelo, anio_inicio=2020, anio_fin=2022,
			imagen_principal='productos/farola.jpg', precio_minimo=100, precio_venta=120,
		)

	def test_selector_exposes_each_step_separately(self):
		response = self.client.get(reverse('catalogo:vehicle_selector_start'))
		self.assertEqual(response.context['step'], 'brand')
		response = self.client.get(reverse('catalogo:vehicle_selector_model', args=[self.marca.pk]))
		self.assertEqual(response.context['step'], 'model')
		response = self.client.get(reverse('catalogo:vehicle_selector_year', args=[self.marca.pk, self.modelo.pk]))
		self.assertEqual(response.context['step'], 'year')
		self.assertEqual(response.context['options'], [2022, 2021, 2020])

	def test_results_return_to_year_selection(self):
		results_url = reverse('catalogo:vehicle_selector_products', args=[self.marca.pk, self.modelo.pk, 2021])
		years_url = reverse('catalogo:vehicle_selector_year', args=[self.marca.pk, self.modelo.pk])
		response = self.client.get(results_url)
		self.assertEqual(response.context['step'], 'results')
		self.assertContains(response, f'href="{years_url}"')
		self.assertContains(response, self.producto.nombre_pieza)

	def test_close_button_returns_to_product_list(self):
		response = self.client.get(reverse('catalogo:vehicle_selector_start'))
		self.assertContains(response, f'href="{reverse("catalogo:producto_list")}"')
		self.assertContains(response, 'aria-label="Cerrar catálogo y volver a productos"')

	def test_product_uses_compatible_model_range_and_creates_a_new_generation(self):
		def product_form(start, end, piece):
			return ProductoForm(
				data={
					'nombre_pieza': piece, 'marca_nombre': 'Mazda', 'modelo_nombre': 'CX-5',
					'categoria_nombre': 'OTROS',
					'anio_inicio': start, 'anio_fin': end, 'precio_minimo': '100',
					'precio_venta': '120', 'activo': True,
				},
				files={'imagen_principal': SimpleUploadedFile('pieza.jpg', b'image', content_type='image/jpeg')},
			)

		compatible = product_form(2021, 2021, 'Espejo')
		self.assertTrue(compatible.is_valid(), compatible.errors)
		self.assertEqual(compatible.save().modelo, self.modelo)

		new_generation = product_form(2023, 2025, 'Bomper')
		self.assertTrue(new_generation.is_valid(), new_generation.errors)
		new_model = new_generation.save().modelo
		self.assertNotEqual(new_model, self.modelo)
		self.assertEqual((new_model.anio_inicio, new_model.anio_fin), (2023, 2025))

	def test_product_list_combines_search_and_year_filters(self):
		from django.contrib.auth import get_user_model
		admin = get_user_model().objects.create_user(username='catalog-admin', password='test', is_staff=True)
		self.client.force_login(admin)
		response = self.client.get(reverse('catalogo:producto_list'), {'q': 'Farola', 'anio': '2021'})
		self.assertEqual(list(response.context['objects']), [self.producto])

		response = self.client.get(reverse('catalogo:producto_list'), {'q': 'Farola', 'anio': '2025'})
		self.assertEqual(list(response.context['objects']), [])


class ProductPaginationTests(TestCase):
    def read_zip(self, response):
        from io import BytesIO
        from zipfile import ZipFile
        self.assertEqual(response.status_code, 200)
        content = b''.join(response.streaming_content)
        return ZipFile(BytesIO(content))

    def test_bulk_download_ignores_page_and_resolves_duplicate_names(self):
        from unittest.mock import patch
        with patch('catalogo.downloads.generate_product_png', return_value=b'generated-png') as generate:
            response = self.client.get(reverse('catalogo:download_catalog'), {'page': 2})
            with self.read_zip(response) as archive:
                self.assertEqual(len(archive.namelist()), 30)
                self.assertEqual(len(set(archive.namelist())), 30)
                self.assertTrue(all(archive.read(name) == b'generated-png' for name in archive.namelist()))
            self.assertEqual(generate.call_count, 30)
            self.assertTrue(all(call.args[1] == 120 for call in generate.call_args_list))

    def test_bulk_filters_and_default_active_products(self):
        from unittest.mock import patch
        product = Producto.objects.get(sku='1')
        category = Categoria.objects.create(nombre='FAROLAS')
        product.categoria = category
        product.activo = False
        product.save()
        params = {
            'q': 'PIEZA', 'marca': product.modelo.marca_id, 'modelo': product.modelo_id,
            'categoria': category.pk, 'anio': 2000, 'activo': '0', 'page': 99,
        }
        with patch('catalogo.downloads.generate_product_png', return_value=b'png') as generate:
            with self.read_zip(self.client.get(reverse('catalogo:download_catalog'), params)) as archive:
                self.assertEqual(len(archive.namelist()), 1)
            self.assertEqual(generate.call_args.args[0].pk, product.pk)
            generate.reset_mock()
            with self.read_zip(self.client.get(reverse('catalogo:download_catalog'))) as archive:
                self.assertEqual(len(archive.namelist()), 29)
            self.assertNotIn(product.pk, [call.args[0].pk for call in generate.call_args_list])
        params['anio'] = 2020
        self.assertEqual(self.client.get(reverse('catalogo:download_catalog'), params).status_code, 400)

    def test_bulk_png_matches_individual_download(self):
        from unittest.mock import patch
        with patch('generador.views._logo_data_uri', return_value=None):
            bulk = self.client.get(reverse('catalogo:download_catalog'), {'q': 'ABC'})
            product = Producto.objects.get(sku='ABC')
            single = self.client.get(reverse('generador:download_product_png', args=[product.pk]), {'precio_publicacion': 120})
        with self.read_zip(bulk) as archive:
            self.assertEqual(archive.read(archive.namelist()[0]), single.content)

    def test_bulk_partial_failure_keeps_other_images_and_reports_errors(self):
        from unittest.mock import patch
        def generate(product, price):
            if product.sku == '1':
                raise ValueError('test failure')
            return b'png'
        with patch('catalogo.downloads.generate_product_png', side_effect=generate), self.assertLogs('catalogo.downloads', level='ERROR'):
            response = self.client.get(reverse('catalogo:download_catalog'))
        with self.read_zip(response) as archive:
            self.assertEqual(len([name for name in archive.namelist() if name.endswith('.png')]), 29)
            self.assertIn('SKU 1 - PIEZA', archive.read('errores.txt').decode())
        self.client.logout()
        self.assertEqual(self.client.get(reverse('catalogo:download_catalog')).status_code, 302)

    def test_page_numbers_scale_and_keep_mobile_window_small(self):
        from django.core.paginator import Paginator
        from .views import _pagination_items

        for total, current, expected in (
            (4, 2, [1, 2, 3, 4]),
            (25, 2, [1, 2, 3, 4, 5, '…', 25]),
            (25, 12, [1, '…', 10, 11, 12, 13, 14, '…', 25]),
            (25, 23, [1, '…', 21, 22, 23, 24, 25]),
        ):
            items = _pagination_items(Paginator(range(total * 25), 25).page(current))
            self.assertEqual([item['number'] for item in items], [
                Paginator.ELLIPSIS if number == '…' else number for number in expected
            ])
            self.assertLessEqual(sum(item['compact'] for item in items), 4)
            self.assertTrue(next(item for item in items if item['number'] == current)['compact'])
        items = _pagination_items(Paginator(range(25000), 25).page(500))
        self.assertLessEqual(len(items), 9)

    def test_pagination_controls_are_accessible_and_keep_all_query_parameters(self):
        first = self.client.get(self.url, {'q': 'PIEZA', 'extra': ['a+b', 'c&d'], 'page': 1})
        self.assertContains(first, 'aria-label="Primera página" aria-disabled="true"')
        self.assertContains(first, 'aria-label="Página anterior" aria-disabled="true"')
        self.assertContains(first, 'aria-current="page" aria-label="Página 1"')
        self.assertContains(first, 'aria-label="Página 2"')
        self.assertContains(first, 'q=PIEZA&amp;extra=a%2Bb&amp;extra=c%26d&amp;page=2')
        last = self.client.get(self.url, {'page': 2})
        self.assertContains(last, 'aria-label="Página siguiente" aria-disabled="true"')
        self.assertContains(last, 'aria-label="Última página" aria-disabled="true"')
        self.assertContains(last, 'aria-label="Primera página" href="?page=1"')

    def setUp(self):
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_user(username='pagination-admin', is_staff=True)
        self.client.force_login(admin)
        marca = Marca.objects.create(nombre='FORD')
        modelo = ModeloVehiculo.objects.create(marca=marca, nombre='F150')
        Producto.objects.bulk_create([
            Producto(sku=sku, nombre_pieza='PIEZA', modelo=modelo, anio_inicio=1997,
                     anio_fin=2003, precio_minimo=100, precio_venta=120)
            for sku in [None, '', 'ABC', *[str(n) for n in range(27, 0, -1)]]
        ])
        self.url = reverse('catalogo:producto_list')

    def test_numeric_order_and_page_size(self):
        first = self.client.get(self.url)
        self.assertEqual([p.sku for p in first.context['objects']], [str(n) for n in range(1, 26)])
        self.assertEqual(first.context['page_obj'].paginator.count, 30)
        self.assertContains(first, 'page=2')
        second = self.client.get(self.url, {'page': 2})
        self.assertEqual([p.sku for p in second.context['objects']][:3], ['26', '27', 'ABC'])
        self.assertEqual(len(second.context['objects']), 5)
        self.assertFalse(second.context['page_obj'].has_next())

    def test_filters_survive_navigation_and_invalid_pages_are_handled(self):
        response = self.client.get(self.url, {'q': 'PIEZA', 'anio': '2000', 'page': 1})
        self.assertContains(response, 'q=PIEZA&amp;anio=2000&amp;page=2')
        for value, expected_page in [('invalid', 1), ('999', 2)]:
            response = self.client.get(self.url, {'page': value})
            self.assertEqual(response.context['page_obj'].number, expected_page)
        empty = self.client.get(self.url, {'q': 'NOT-FOUND'})
        self.assertEqual(len(empty.context['objects']), 0)
        self.assertNotContains(empty, 'aria-label="Páginas de productos"')


class ProtectedDeletionTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        self.client.force_login(get_user_model().objects.create_user(username='delete-admin', is_staff=True))
        self.marca = Marca.objects.create(nombre='F')
        self.modelo = ModeloVehiculo.objects.create(marca=self.marca, nombre='F150_LOBO', anio_inicio=1997, anio_fin=2003)

    def test_brand_with_model_shows_actionable_message(self):
        response = self.client.post(reverse('catalogo:marca_delete', args=[self.marca.pk]))
        self.assertContains(response, 'No se eliminó ningún dato.')
        self.assertContains(response, reverse('catalogo:modelovehiculo_update', args=[self.modelo.pk]))
        self.assertNotContains(response, 'Confirmar eliminación')
        self.assertTrue(Marca.objects.filter(pk=self.marca.pk).exists())
        self.assertTrue(ModeloVehiculo.objects.filter(pk=self.modelo.pk).exists())

    def test_model_with_product_remains_intact(self):
        product = Producto.objects.create(nombre_pieza='FAROLA', modelo=self.modelo, anio_inicio=1997,
                                         anio_fin=2003, precio_minimo=100, precio_venta=120)
        response = self.client.post(reverse('catalogo:modelovehiculo_delete', args=[self.modelo.pk]))
        self.assertContains(response, reverse('catalogo:producto_update', args=[product.pk]))
        self.assertTrue(ModeloVehiculo.objects.filter(pk=self.modelo.pk).exists())
        self.assertTrue(Producto.objects.filter(pk=product.pk).exists())

    def test_unreferenced_brand_can_still_be_deleted(self):
        brand = Marca.objects.create(nombre='SIN MODELOS')
        url = reverse('catalogo:marca_delete', args=[brand.pk])
        self.assertContains(self.client.get(url), 'Confirmar eliminación')
        self.assertTrue(Marca.objects.filter(pk=brand.pk).exists())
        self.assertRedirects(self.client.post(url), reverse('catalogo:marca_list'))
        self.assertFalse(Marca.objects.filter(pk=brand.pk).exists())


class ProductCategoryTests(TestCase):
    def test_category_is_a_required_select_with_requested_options(self):
        form = ProductoForm()
        html = str(form['categoria_nombre'])
        self.assertIn('<select', html)
        self.assertTrue(form.fields['categoria_nombre'].required)
        self.assertEqual(list(form.fields['categoria_nombre'].choices), [
            ('', 'Selecciona una categoría'),
            *[(name, name) for name in (
                'FAROLAS', 'STOPS', 'PERSIANAS / PARRILLAS', 'EXPLORADORAS',
                'LUCES Y DIRECCIONALES', 'CARROCERÍA', 'INTERIOR', 'ELÉCTRICO',
                'SUSPENSIÓN', 'ESCAPE', 'EMBLEMAS Y ACCESORIOS', 'OTROS',
            )],
        ])

    def test_saving_reuses_existing_category_and_rejects_free_text(self):
        category = Categoria.objects.create(nombre='Stops')
        data = {
            'nombre_pieza': 'STOP LED', 'marca_nombre': 'FORD', 'modelo_nombre': 'F150',
            'categoria_nombre': 'STOPS', 'anio_inicio': 1997, 'anio_fin': 2003,
            'precio_minimo': '100', 'precio_venta': '120', 'activo': True,
        }
        form = ProductoForm(data=data, files={
            'imagen_principal': SimpleUploadedFile('stop.jpg', b'image', content_type='image/jpeg'),
        })
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save(commit=False)
        self.assertEqual(product.categoria, category)
        self.assertEqual(Categoria.objects.filter(nombre__iexact='STOPS').count(), 1)
        product.pk = 123
        self.assertEqual(ProductoForm(instance=product)['categoria_nombre'].value(), 'STOPS')
        for invalid in ('', 'CATEGORIA INVENTADA'):
            form = ProductoForm(data={**data, 'categoria_nombre': invalid})
            self.assertFalse(form.is_valid())
            self.assertIn('categoria_nombre', form.errors)
