import struct
import xml.etree.ElementTree as ET
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

import resvg
from django.test import RequestFactory, SimpleTestCase

from .views import build_product_svg, download_product_png, download_product_svg, product_download_filename
from .layout import wrap_text


class DownloadProductPNGTests(SimpleTestCase):
    def setUp(self):
        self.producto = SimpleNamespace(
            modelo=SimpleNamespace(marca=SimpleNamespace(nombre='Toyota'), nombre='Hilux'),
            nombre_pieza='Parachoques', anio_inicio=2020, anio_fin=2025,
            precio_minimo=Decimal('100000'), precio_venta=Decimal('150000'),
            imagen_principal=None, observaciones='Producto de prueba', sku='TEST-1',
        )

    def download(self, price='150000', view=download_product_png):
        request = RequestFactory().get('/', {'precio_publicacion': price})
        request.user = SimpleNamespace(is_authenticated=True)
        with patch('generador.views.get_object_or_404', return_value=self.producto):
            with patch('generador.views._logo_data_uri', return_value=None):
                return view(request, pk=1)

    def render_fixture(self, width, height, content=''):
        tree = resvg.usvg.Tree.from_str(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'{content}</svg>', resvg.usvg.Options.default(),
        )
        return bytes(resvg.render(tree, (1, 0, 0, 0, 1, 0)))

    def test_png_has_content_and_expected_dimensions(self):
        response = self.download()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="TOYOTA_HILUX_2020_2025_PARACHOQUES.png"')
        self.assertTrue(response.content.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(struct.unpack('>II', response.content[16:24]), (1600, 900))
        # The old degenerate transform produced an entirely empty canvas.
        self.assertNotEqual(response.content, self.render_fixture(1600, 900))

    def test_price_text_is_rendered(self):
        self.assertNotEqual(self.download('150000').content, self.download('200000').content)

    def test_embedded_product_photo_is_rendered(self):
        photo = self.render_fixture(10, 10, '<rect width="10" height="10" fill="red"/>')
        self.producto.imagen_principal = SimpleNamespace(name='productos/test.png')
        with patch('generador.views.default_storage.open', return_value=BytesIO(photo)):
            with_photo = self.download().content
        # Keep the image element but substitute a transparent PNG of the same size.
        transparent = self.render_fixture(10, 10)
        with patch('generador.views.default_storage.open', return_value=BytesIO(transparent)):
            without_photo = self.download().content
        self.assertNotEqual(with_photo, without_photo)

    def test_price_below_minimum_is_rejected(self):
        self.assertEqual(self.download('1').status_code, 400)

    def test_download_names_use_current_product_details_for_both_formats(self):
        self.producto.modelo.marca.nombre = 'Ford'
        self.producto.modelo.nombre = 'F150_LOBO'
        self.producto.anio_inicio = 1997
        self.producto.anio_fin = 2003
        self.producto.nombre_pieza = 'PERSIANA SUPERIOR + PERSIANA BUMPER EN ACERO INOXIDABLE'
        expected = 'FORD_F150_LOBO_1997_2003_PERSIANA_SUPERIOR_+_PERSIANA_BUMPER_EN_ACERO_INOXIDABLE'
        for extension, view in (('png', download_product_png), ('svg', download_product_svg)):
            self.assertEqual(
                self.download(view=view)['Content-Disposition'],
                f'attachment; filename="{expected}.{extension}"',
            )

    def test_filename_handles_accents_and_unsafe_characters(self):
        from urllib.parse import unquote

        self.producto.nombre_pieza = '  DIRECCIÓN / SOPORTE: "LED"\r\n+ TRASERO?  '
        expected = 'TOYOTA_HILUX_2020_2025_DIRECCIÓN_SOPORTE_LED_+_TRASERO.svg'
        self.assertEqual(product_download_filename(self.producto, 'svg'), expected)
        header = self.download(view=download_product_svg)['Content-Disposition']
        self.assertIn("filename*=utf-8''", header.lower())
        self.assertEqual(unquote(header.split("''", 1)[1]), expected)

    def test_long_text_flows_without_losing_content_or_overlapping(self):
        self.producto.nombre_pieza = 'PARRILLA_PRINCIPAL_INFERIOR_' + 'W' * 170
        self.producto.modelo.nombre = 'MODELO_' * 21
        self.producto.observaciones = ('Incluye tornillería & soporte <original>.\n' * 30).strip()
        self.producto.sku = 'SKU_' * 25
        with patch('generador.views._logo_data_uri', return_value=None):
            svg = ET.fromstring(build_product_svg(self.producto, Decimal('9999999999.99')))
        ns = {'s': 'http://www.w3.org/2000/svg'}
        height = int(svg.attrib['height'])
        self.assertGreater(height, 900)
        previous_y = 0
        fields = {}
        for text in svg.findall('s:text', ns):
            spans = text.findall('s:tspan', ns)
            if not spans:
                continue
            fields[text.attrib['class']] = ''.join(span.text or '' for span in spans)
            for span in spans:
                y = int(span.attrib['y'])
                self.assertGreater(y, previous_y)
                self.assertLess(y, height - 20)
                previous_y = y
        for css_class, original in (
            ('piece', self.producto.nombre_pieza),
            ('model', self.producto.modelo.nombre),
            ('note', self.producto.observaciones),
            ('sku', 'SKU ' + self.producto.sku),
        ):
            self.assertEqual(''.join(fields[css_class].split()), ''.join(original.split()))
        response = self.download()
        self.assertGreater(struct.unpack('>II', response.content[16:24])[1], 900)

    def test_wrapping_identifiers_words_and_explicit_newlines(self):
        for value in ('PARRILLA_PRINCIPAL_INFERIOR_BLANCA', 'W' * 200, 'Árbol & soporte <original>'):
            lines = wrap_text(value, 30)
            self.assertEqual(''.join(''.join(lines).split()), ''.join(value.split()))
        self.assertTrue(all(len(line) <= 16 for line in wrap_text('W' * 200, 30)))
        self.assertEqual(wrap_text('Primera\n\nTercera', 22), ['Primera', '', 'Tercera'])
