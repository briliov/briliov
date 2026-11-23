from __future__ import annotations

import base64
import colorsys
from pathlib import Path
import xml.etree.ElementTree as ET

from profile_sync.config import BADGES_DIR


def adjust_color_for_theme(hex_str: str, theme: str) -> str:
    """Adapt icon color contrast separately for light and dark GitHub themes."""
    clean_hex = hex_str.lstrip('#')
    if len(clean_hex) != 6:
        return '#24292f' if theme == 'light' else '#f0f6fc'

    r, g, b = (int(clean_hex[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    if theme == 'light':
        if s < 0.12 and l > 0.45:
            return '#24292f'
        if l > 0.48:
            l = 0.42
    else:
        if s < 0.12 and l < 0.65:
            return '#f0f6fc'
        if l < 0.65:
            l = 0.68

    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return f'#{int(nr * 255):02x}{int(ng * 255):02x}{int(nb * 255):02x}'


def colorize_svg(svg_bytes: bytes, hex_color: str) -> str:
    try:
        ET.register_namespace('', 'http://www.' + 'w3.org/2000/svg')
        root = ET.fromstring(svg_bytes)
        root.set('fill', hex_color)
        shapes = ('path', 'circle', 'rect', 'polygon', 'ellipse')
        for elem in root.iter():
            if elem.tag.endswith('style'):
                elem.text = ''
            if 'style' in elem.attrib:
                del elem.attrib['style']
            tag_name = elem.tag.split('}')[-1]
            fill_val = elem.attrib.get('fill', '').lower()
            if fill_val not in ('none', 'transparent'):
                if fill_val or tag_name in shapes:
                    elem.set('fill', hex_color)
            stroke_val = elem.attrib.get('stroke', '').lower()
            if stroke_val and stroke_val not in ('none', 'transparent'):
                elem.set('stroke', hex_color)
        encoded = base64.b64encode(ET.tostring(root, encoding='utf-8')).decode('ascii')
        return f'data:image/svg+xml;base64,{encoded}'
    except ET.ParseError:
        encoded = base64.b64encode(svg_bytes).decode('ascii')
        return f'data:image/svg+xml;base64,{encoded}'


def recolor_data_uri(data_uri: str, raw_color: str, theme: str) -> str:
    """Recolor an embedded SVG data URI for the target theme if applicable."""
    prefix = 'data:image/svg+xml;base64,'
    if not data_uri.startswith(prefix) or not raw_color.startswith('#'):
        return data_uri
    svg_bytes = base64.b64decode(data_uri[len(prefix) :])
    themed_hex = adjust_color_for_theme(raw_color, theme)
    return colorize_svg(svg_bytes, themed_hex)


def create_themed_badges(
    topic: str,
    icon_data: str,
    raw_color: str,
    display_label: str | None = None,
) -> tuple[Path, Path]:
    """Generate both -light.svg and -dark.svg badges for GitHub <picture>."""
    label = (display_label or topic.replace('-', ' ')).upper()
    char_width = 9.2
    text_width = int(len(label) * char_width)
    icon_offset = 25
    total_width = text_width + icon_offset + 28
    text_x = (13 + icon_offset) + (text_width / 2)
    svg_ns = 'http://www.' + 'w3.org/2000/svg'

    themes = {
        'light': ('#f6f8fa', '#d0d7de', '#24292f'),
        'dark': ('#161b22', '#30363d', '#f0f6fc'),
    }
    paths: dict[str, Path] = {}

    for theme, (bg, border, text_fill) in themes.items():
        themed_icon = recolor_data_uri(icon_data, raw_color, theme)
        lines = [
            f'<svg xmlns="{svg_ns}" width="{total_width}" height="30" role="img" aria-label="{label}">',
            f'  <rect x="0.5" y="0.5" width="{total_width - 1}" height="29" rx="6" fill="{bg}" stroke="{border}" stroke-width="1" />',
            f'  <image x="12" y="7.5" width="15" height="15" href="{themed_icon}" />',
            f'  <text x="{text_x:.1f}" y="19" fill="{text_fill}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
            f'font-size="11" font-weight="800" text-anchor="middle" letter-spacing="1.5">{label}</text>',
            '</svg>',
        ]
        out_path = BADGES_DIR / f'{topic}-{theme}.svg'
        out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        paths[theme] = out_path

    return paths['light'], paths['dark']
