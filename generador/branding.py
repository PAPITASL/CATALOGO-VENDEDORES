"""Shared export branding. Original product files are never written."""
import base64
import logging
from io import BytesIO
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageChops, ImageOps

RED = '#ed0012'
BLACK = '#171717'
GRAY = '#454545'
SILVER = '#bcbcbc'
logger = logging.getLogger(__name__)


def load_logo():
    path = Path(settings.LUJOSHOP_LOGO_PATH)
    if not path.is_file():
        logger.warning('Falta el logo oficial de fondo blanco: %s', path)
        return None
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGB')
        # Trim only near-white external margins, preserving all artwork.
        difference = ImageChops.difference(image, Image.new('RGB', image.size, 'white'))
        mask = difference.convert('L').point(lambda value: 255 if value > 12 else 0)
        bounds = mask.getbbox()
        if bounds:
            left, top, right, bottom = bounds
            padding = max(2, round(max(image.size) * .006))
            image = image.crop((max(0, left-padding), max(0, top-padding),
                                min(image.width, right+padding), min(image.height, bottom+padding)))
        return image


class Branding:
    def __init__(self, width, height, max_height=None):
        self.logo = load_logo()
        self.margin = round(width * .025)
        self.width = round(width * .20)
        self.height = (round(self.width * self.logo.height / self.logo.width)
                       if self.logo else 0)
        # Keep unusually tall assets within the header budget without distortion.
        limit = max_height if max_height is not None else height * .24
        if self.height > limit:
            self.height = round(limit)
            self.width = round(self.height * self.logo.width / self.logo.height)
        self.x = width - self.margin - self.width
        self.y = self.margin
        self.bottom = self.y + self.height + self.margin if self.logo else 0

    def apply(self, canvas):
        if self.logo:
            logo = self.logo.resize((self.width, self.height), Image.Resampling.LANCZOS)
            canvas.paste(logo, (self.x, self.y))
        return canvas

    def data_uri(self):
        if not self.logo:
            return None
        output = BytesIO()
        self.logo.save(output, 'PNG')
        return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')

    def svg(self, href):
        if not href:
            return ''
        return (f'<image href="{href}" x="{self.x}" y="{self.y}" '
                f'width="{self.width}" height="{self.height}" preserveAspectRatio="xMidYMid meet"/>')
