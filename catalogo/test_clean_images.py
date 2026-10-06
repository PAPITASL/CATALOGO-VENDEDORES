from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont

from .clean_images import compose_jpeg, compose_heading_jpeg, heading_lines, resize_photo, process_next_image
from .models import CatalogImageJob, CatalogImageItem, Marca, ModeloVehiculo, Producto


def cutout():
    image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    image.paste((200, 40, 20, 255), (30, 10, 70, 90))
    stream = BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


class CleanImageTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username='image-admin', is_staff=True)
        self.client.force_login(self.user)
        brand = Marca.objects.create(nombre='FORD')
        model = ModeloVehiculo.objects.create(marca=brand, nombre='F150_LOBO')
        self.products = Producto.objects.bulk_create([
            Producto(modelo=model, nombre_pieza='KIT + SOPORTE', sku=str(n),
                     anio_inicio=1997, anio_fin=2003, precio_minimo=100, precio_venta=120,
                     imagen_principal='original.png', activo=n != 0)
            for n in range(30)
        ])
        self.start_url = reverse('catalogo:clean_image_start')

    def start_job(self, params=''):
        response = self.client.post(self.start_url + params)
        self.assertEqual(response.status_code, 302)
        return CatalogImageJob.objects.get(owner=self.user, active=True)

    def test_snapshot_all_pages_including_inactive_matches_list_and_is_idempotent(self):
        job = self.start_job('?page=2')
        self.assertEqual(job.items.count(), 30)
        self.assertEqual(job.items.values('filename').distinct().count(), 30)
        self.assertTrue(job.items.first().filename.startswith('FORD_F150_LOBO_1997-2003_KIT_+_SOPORTE'))
        self.client.post(self.start_url)
        self.assertEqual(CatalogImageJob.objects.count(), 1)

    def test_filters_without_external_service_configuration(self):
        job = self.start_job('?activo=0&anio=2000&q=KIT&page=2')
        self.assertEqual(job.items.count(), 1)
        self.assertEqual(job.items.first().product_id, self.products[0].pk)

    def test_output_is_white_800_600_jpeg(self):
        default_storage.save('original.png', ContentFile(cutout()))
        output = resize_photo('original.png')
        with Image.open(BytesIO(output)) as image:
            self.assertEqual(image.size, (800, 600))
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
            self.assertNotEqual(image.getpixel((400, 300)), (255, 255, 255))

    def test_worker_persists_success_and_error_and_downloads_without_regeneration(self):
        job = self.start_job('?activo=0')
        with patch('catalogo.clean_images.resize_photo', return_value=compose_jpeg(cutout())) as edit:
            self.assertTrue(process_next_image())
            self.assertFalse(process_next_image())
            self.assertEqual(edit.call_count, 1)
        job.refresh_from_db()
        self.assertFalse(job.active)
        item = job.items.get()
        self.assertEqual(item.status, 'done')
        self.assertTrue(default_storage.exists(item.image.name))
        response = self.client.get(reverse('catalogo:clean_image_download', args=[job.pk, item.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\xff\xd8'))
        response = self.client.get(reverse('catalogo:clean_image_zip', args=[job.pk]))
        with ZipFile(BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertEqual(archive.namelist(), [item.filename])
        self.products[0].refresh_from_db()
        self.assertEqual(self.products[0].imagen_principal.name, 'original.png')
        failed_job = self.start_job('?activo=0')
        with patch('catalogo.clean_images.resize_photo', side_effect=FileNotFoundError), self.assertLogs('catalogo.clean_images'):
            process_next_image()
        self.assertEqual(failed_job.items.get().status, 'error')

    def test_owner_isolation_and_post_requires_csrf(self):
        job = self.start_job('?activo=0')
        other = get_user_model().objects.create_user(username='other-admin', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('catalogo:clean_image_job', args=[job.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('catalogo:clean_image_zip', args=[job.pk])).status_code, 404)
        from django.test import Client
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(other)
        self.assertEqual(protected.post(self.start_url).status_code, 403)

    def test_empty_filter_creates_no_job(self):
        response = self.client.post(self.start_url + '?q=DOES_NOT_EXIST')
        self.assertContains(response, 'No hay productos')
        self.assertEqual(CatalogImageJob.objects.count(), 0)

    def test_opaque_landscape_and_portrait_preserve_full_photo(self):
        for size, margin, edge in (
            ((400, 100), (400, 0), (5, 205)),
            ((100, 400), (0, 300), (330, 5)),
        ):
            source = Image.new('RGB', size, (20, 100, 200))
            buffer = BytesIO()
            source.save(buffer, 'PNG')
            result = Image.open(BytesIO(compose_jpeg(buffer.getvalue())))
            self.assertEqual(result.size, (800, 600))
            self.assertEqual(result.getpixel(margin), (255, 255, 255))
            for actual, expected in zip(result.getpixel(edge), (20, 100, 200)):
                self.assertLessEqual(abs(actual - expected), 3)

    def test_browser_can_process_without_worker_or_key(self):
        default_storage.save('original.png', ContentFile(cutout()))
        job = self.start_job('?activo=0')
        url = reverse('catalogo:clean_image_process', args=[job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(job.items.get().status, 'done')
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(job.items.count(), 1)

    def test_seller_job_snapshots_heading_and_downloads(self):
        default_storage.save('original.png', ContentFile(cutout()))
        url = reverse('catalogo:seller_image_start') + '?activo=0'
        self.assertContains(self.client.get(url), 'Imágenes para vendedores')
        self.assertEqual(self.client.post(url).status_code, 302)
        job = CatalogImageJob.objects.get(active=True)
        self.assertTrue(job.with_heading)
        item = job.items.get()
        self.assertEqual(item.heading, {'piece': 'KIT + SOPORTE', 'vehicle': 'FORD · F150_LOBO · 1997-2003'})
        Producto.objects.filter(pk=item.product_id).update(nombre_pieza='Nombre posterior')
        with patch('catalogo.clean_images.compose_heading_jpeg', wraps=compose_heading_jpeg) as compose:
            process_next_image(job.pk)
            self.assertEqual(compose.call_args.args[1]['piece'], 'KIT + SOPORTE')
        item.refresh_from_db()
        self.assertEqual(item.status, 'done')
        response = self.client.get(reverse('catalogo:clean_image_download', args=[job.pk, item.pk]))
        data = b''.join(response.streaming_content)
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.size, (800, 600))
            self.assertEqual(image.format, 'JPEG')
            self.assertLess(min(image.crop((24, 16, 776, 80)).convert('L').getdata()), 100)
        response = self.client.get(reverse('catalogo:clean_image_zip', args=[job.pk]))
        with ZipFile(BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertEqual(archive.read(item.filename), data)

    def test_active_plain_job_does_not_silently_replace_seller_request(self):
        job = self.start_job('?activo=0')
        self.assertFalse(job.with_heading)
        response = self.client.post(reverse('catalogo:seller_image_start'))
        self.assertContains(response, 'Continuar generación en curso')
        self.assertEqual(CatalogImageJob.objects.count(), 1)

    def test_heading_wrap_preserves_long_names_and_accents(self):
        draw = ImageDraw.Draw(Image.new('RGB', (800, 600)))
        font = ImageFont.load_default(size=30)
        for text in ['ÁÉÍÓÚ ñ soporte de dirección ' * 8, 'M' * 200]:
            lines = heading_lines(draw, text, font)
            self.assertEqual(''.join(lines).replace(' ', ''), text.replace(' ', ''))
            self.assertTrue(all(draw.textlength(line, font=font) <= 752 for line in lines))
        raw = BytesIO()
        Image.new('RGB', (400, 100), (200, 40, 20)).save(raw, 'PNG')
        data = compose_heading_jpeg(raw.getvalue(), {'piece': 'M' * 200, 'vehicle': 'W' * 253})
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.size, (800, 600))
            # Both horizontal photo edges survive below the heading.
            for x in (1, 798):
                self.assertTrue(any(image.getpixel((x, y))[0] > 180 and image.getpixel((x, y))[1] < 60
                                    for y in range(220, 600)))
