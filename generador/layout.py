"""SVG text flow with conservative widths for the sans-serif font family."""

import re
import unicodedata
from html import escape


def text_width(text, size):
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in ('W', 'F') or char in 'MWmw@%':
            width += 1.1
        elif char in ' ilI.,:;!\'|':
            width += 0.4
        elif char.isupper():
            width += 0.85
        else:
            width += 0.7
    return width * size


def wrap_text(text, size, width=540):
    """Preserve explicit newlines and break long identifiers without losing text."""
    lines = []
    for paragraph in str(text).split('\n'):
        line = ''
        # Underscores and hyphens are natural breaks in product identifiers.
        for token in re.findall(r'[^\s_-]+[_-]*|[_-]+|[^\S\n]+', paragraph):
            if line and text_width(line + token, size) > width:
                lines.append(line.rstrip())
                line = ''
            for char in token:
                if not line and char.isspace():
                    continue
                if line and text_width(line + char, size) > width:
                    lines.append(line.rstrip())
                    line = ''
                line += char
        lines.append(line.rstrip())
    return lines


class TextFlow:
    def __init__(self, y=110):
        self.y = y
        self.elements = []

    def text(self, value, css_class, size, gap=16):
        lines = wrap_text(value, size)
        spans = []
        for line in lines:
            self.y += size
            spans.append(f'<tspan x="1000" y="{self.y}">{escape(line)}</tspan>')
            self.y += round(size * 0.25)
        self.elements.append(f'<text class="{css_class}">{"".join(spans)}</text>')
        self.y += gap

    def field(self, label, value, css_class, size):
        self.text(label, 'label', 16, gap=8)
        self.text(value, css_class, size, gap=24)
