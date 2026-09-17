from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from .forms import ProductoForm
from .models import Marca, ModeloVehiculo, Producto


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
