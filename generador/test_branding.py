"""Geometry tests use a synthetic color swatch, never a replacement logo."""
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET

from django.test import SimpleTestCase
from PIL import Image

from catalogo.clean_images import compose_jpeg, compose_heading_jpeg
from .branding import Branding
from .views import build_product_svg, generate_product_png


class BrandingTests(SimpleTestCase):
    def setUp(self):
        self.swatch = Image.new('RGB', (360, 200), '#ed0012')
        self.mock = patch('generador.branding.load_logo', return_value=self.swatch)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        raw = BytesIO()
        Image.new('RGB', (400, 300), '#1266aa').save(raw, 'PNG')
        self.raw = raw.getvalue()

    def test_jpg_templates_reserve_logo_and_preserve_size_and_photo(self):
        branding = Branding(800, 600)
        for data in (compose_jpeg(self.raw), compose_heading_jpeg(self.raw, {
                'piece': 'SOPORTE ' * 12, 'vehicle': 'FORD 2000-2020'})):
            image = Image.open(BytesIO(data))
            self.assertEqual(image.size, (800, 600))
            self.assertEqual(image.getpixel((799, 0)), (255, 255, 255))
            red = image.getpixel((branding.x + 50, branding.y + 20))
            self.assertGreater(red[0], 220)
            self.assertLess(red[1], 10)
            self.assertGreater(image.getpixel((400, 450))[2], 150)
        self.assertEqual(self.swatch.size, (360, 200))

    def test_svg_png_keep_original_dimensions_and_separate_text(self):
        product = SimpleNamespace(
            modelo=SimpleNamespace(marca=SimpleNamespace(nombre='Ford'), nombre='F150'),
            anio_inicio=2000, anio_fin=2020, nombre_pieza='Soporte',
            precio_minimo=Decimal('100'), observaciones='Medidas 10 x 20 cm',
            sku='ABC', imagen_principal=None)
        svg = ET.fromstring(build_product_svg(product, Decimal('200')))
        self.assertEqual((svg.attrib['width'], svg.attrib['height']), ('1600', '900'))
        logo = svg.find('{http://www.w3.org/2000/svg}image')
        self.assertTrue(logo.attrib['href'].startswith('data:image/png;base64,'))
        self.assertEqual(float(logo.attrib['x']) + float(logo.attrib['width']), 1560)
        bottom = float(logo.attrib['y']) + float(logo.attrib['height'])
        for span in svg.findall('.//{http://www.w3.org/2000/svg}tspan'):
            self.assertGreater(float(span.attrib['y']), bottom)
        png = Image.open(BytesIO(generate_product_png(product, Decimal('200'))))
        self.assertEqual(png.size, (1600, 900))
        self.assertEqual(png.getpixel((0, 0)), (255, 255, 255, 255))

    def test_missing_logo_has_no_recreated_fallback(self):
        with patch('generador.branding.load_logo', return_value=None):
            branding = Branding(800, 600)
            self.assertEqual(branding.bottom, 0)
            self.assertIsNone(branding.data_uri())
            self.assertEqual(branding.svg(None), '')
