from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Categoria, Marca, ModeloVehiculo, Producto


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ProductNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(username='navigation', is_staff=True)
        brand = Marca.objects.create(nombre='FORD')
        cls.model = ModeloVehiculo.objects.create(
            marca=brand, nombre='F150', anio_inicio=1997, anio_fin=2003)
        cls.category = Categoria.objects.create(nombre='OTROS')
        Producto.objects.bulk_create([
            Producto(nombre_pieza='PIEZA', modelo=cls.model, categoria=cls.category,
                     anio_inicio=1997, anio_fin=2003, precio_minimo=100,
                     precio_venta=120, imagen_principal='productos/existing.jpg')
            for _ in range(591)
        ])

    def setUp(self):
        self.client.force_login(self.admin)
        self.list_url = reverse('catalogo:producto_list')
        self.create_url = reverse('catalogo:producto_create')
        self.product = Producto.objects.order_by('pk').first()
        self.edit_url = reverse('catalogo:producto_update', args=[self.product.pk])

    def data(self, **changes):
        return {
            'nombre_pieza': 'PIEZA NUEVA', 'sku': '0', 'marca_nombre': 'FORD',
            'modelo_nombre': 'F150', 'categoria_nombre': 'OTROS',
            'anio_inicio': 1997, 'anio_fin': 2003, 'precio_minimo': 100,
            'precio_venta': 120, 'activo': 'on', **changes,
        }

    def create(self):
        return self.client.post(self.create_url, self.data(
            sku='', navigation='page=10&q=no-coincide',
            imagen_principal=SimpleUploadedFile('test.jpg', b'image', content_type='image/jpeg')))

    def test_create_returns_to_last_page_and_appends_regardless_of_sku(self):
        original = list(Producto.objects.order_by('pk').values())
        response = self.create()
        self.assertRedirects(response, self.list_url + '?page=24')
        self.assertTrue(list(get_messages(response.wsgi_request)))
        listing = self.client.get(response.url)
        self.assertEqual(list(listing.context['objects'])[-1], Producto.objects.latest('pk'))
        self.assertEqual(original, list(Producto.objects.order_by('pk').values())[:591])

    def test_create_crosses_page_boundary_dynamically(self):
        for _ in range(9):
            self.assertEqual(self.create().url, self.list_url + '?page=24')
        self.assertRedirects(self.create(), self.list_url + '?page=25')
        self.assertEqual(Producto.objects.count(), 601)

    def test_edit_returns_to_pages_10_and_24(self):
        for page in (10, 24):
            product = Producto.objects.order_by('pk')[(page - 1) * 25]
            url = reverse('catalogo:producto_update', args=[product.pk])
            self.assertRedirects(self.client.post(url, self.data(
                sku='', navigation=f'page={page}')), self.list_url + f'?page={page}')

    def test_edit_preserves_filters_and_repeated_query_parameters(self):
        navigation = f'page=10&q=PIEZA&marca={self.model.marca_id}&modelo={self.model.pk}&categoria={self.category.pk}&anio=2000&activo=1&extra=a%2Bb&extra=c%26d'
        response = self.client.post(self.edit_url, self.data(navigation=navigation))
        self.assertRedirects(response, self.list_url + '?' + navigation)

    def test_missing_origin_page_falls_back_to_last_filtered_page(self):
        response = self.client.post(self.edit_url, self.data(navigation='q=NUEVA&page=24'))
        self.assertRedirects(response, self.list_url + '?q=NUEVA&page=1')

    def test_cancel_links_preserve_origin_and_do_not_write(self):
        original = list(Producto.objects.order_by('pk').values())
        for url in (self.create_url, self.edit_url):
            response = self.client.get(url, {'page': 24, 'q': 'PIEZA'})
            self.assertContains(response, f'href="{self.list_url}?page=24&amp;q=PIEZA"')
            self.assertEqual(self.client.get(response.context['cancel_url']).status_code, 200)
        self.assertEqual(original, list(Producto.objects.order_by('pk').values()))

    def test_validation_retains_data_and_navigation_until_retry(self):
        for url in (self.create_url, self.edit_url):
            data = self.data(precio_venta=50, navigation='page=10&q=PIEZA')
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertEqual(response.context['form']['nombre_pieza'].value(), 'PIEZA NUEVA')
            self.assertContains(response, 'name="navigation" value="page=10&amp;q=PIEZA"')
            self.assertEqual(response.context['cancel_url'], self.list_url + '?page=10&q=PIEZA')
        self.assertEqual(Producto.objects.count(), 591)
        self.product.refresh_from_db()
        self.assertEqual(self.product.precio_venta, 120)
        self.assertRedirects(self.client.post(self.edit_url, self.data(
            navigation='page=10&q=PIEZA')), self.list_url + '?page=10&q=PIEZA')

    def test_links_carry_context_and_redirects_are_internal(self):
        response = self.client.get(self.list_url, {'page': 24, 'q': 'PIEZA'})
        self.assertContains(response, f'{self.create_url}?page=24&amp;q=PIEZA')
        product = list(response.context['objects'])[0]
        edit = reverse('catalogo:producto_update', args=[product.pk])
        self.assertContains(response, f'{edit}?page=24&amp;q=PIEZA')
        response = self.client.post(self.edit_url, self.data(
            navigation='page=10&next=https%3A%2F%2Fevil.example'))
        self.assertEqual(urlsplit(response.url).path, self.list_url)
        self.assertEqual(urlsplit(response.url).netloc, '')
        self.assertEqual(parse_qs(urlsplit(response.url).query)['page'], ['10'])
