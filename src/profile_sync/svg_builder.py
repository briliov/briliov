from __future__ import annotations

import base64
from pathlib import Path
import xml.etree.ElementTree as ET

from profile_sync.config import BADGES_DIR


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
        encoded = base64.b64encode(ET.tostring(root, encoding='utf-8')).decode(
            'ascii'
        )
        return f'data:image/svg+xml;base64,{encoded}'
    except ET.ParseError:
        encoded = base64.b64encode(svg_bytes).decode('ascii')
        return f'data:image/svg+xml;base64,{encoded}'


def create_svg_badge(
    topic: str, icon_data: str, display_label: str | None = None
) -> Path:
    label = (display_label or topic.replace('-', ' ')).upper()
    char_width = 9.2
    text_width = int(len(label) * char_width)
    icon_offset = 25
    total_width = text_width + icon_offset + 28
    text_x = (13 + icon_offset) + (text_width / 2)
    svg_ns = 'http://www.' + 'w3.org/2000/svg'
    lines = [
        f'<svg xmlns="{svg_ns}" width="{total_width}" height="30" role="img" aria-label="{label}">',
        f'  <rect width="{total_width}" height="30" fill="#000000" />',
        f'  <image x="12" y="7.5" width="15" height="15" href="{icon_data}" />',
        f'  <text x="{text_x:.1f}" y="19" fill="#ffffff" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="11" font-weight="800" text-anchor="middle" letter-spacing="1.5">{label}</text>',
        '</svg>',
    ]
    badge_path = BADGES_DIR / f'{topic}.svg'
    badge_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return badge_path
