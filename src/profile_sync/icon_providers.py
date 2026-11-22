from __future__ import annotations

import base64
from io import BytesIO
import logging
import urllib.error
import urllib.request
from PIL import Image

from profile_sync.config import (
    CUSTOM_ICONS_DIR, DEVICON_CDN_URL, EXPLORE_RAW_URL, ICON_SIZE, SIMPLE_ICONS_URL
)
from profile_sync.svg_builder import colorize_svg

logger = logging.getLogger(__name__)


def _fetch_custom_svg(topic: str, brand_colors: dict[str, str]) -> tuple[str, str, str] | None:
    custom_path = CUSTOM_ICONS_DIR / f'{topic}.svg'
    if custom_path.is_file():
        clean_name = topic.replace('-', '')
        target_color = brand_colors.get(clean_name, '#ffffff')
        return (colorize_svg(custom_path.read_bytes(), target_color), f'custom_icons/{topic}.svg', target_color)
    return None


def _fetch_devicon_svg(topic: str, brand_colors: dict[str, str]) -> tuple[str, str, str] | None:
    clean_name = topic.replace('-', '')
    target_color = brand_colors.get(clean_name, '#ffffff')
    for variant in ('plain', 'line', 'original'):
        url = f'{DEVICON_CDN_URL}/{clean_name}/{clean_name}-{variant}.svg'
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    return (colorize_svg(response.read(), target_color), f'{clean_name}-{variant}.svg', target_color)
        except urllib.error.HTTPError:
            continue
        except Exception as exc:
            logger.warning('Error fetching Devicon for %s: %s', topic, exc)
            break
    return None


def _fetch_simple_icon_svg(topic: str, brand_colors: dict[str, str]) -> tuple[str, str, str] | None:
    clean_name = topic.replace('-', '')
    target_color = brand_colors.get(clean_name, '#ffffff')
    url = f'{SIMPLE_ICONS_URL}/{clean_name}.svg'
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status == 200:
                return (colorize_svg(response.read(), target_color), f'{clean_name}.svg', target_color)
    except urllib.error.HTTPError:
        return None
    except Exception as exc:
        logger.warning('Error fetching SimpleIcon for %s: %s', topic, exc)
    return None


def _fetch_explore_png(topic: str) -> tuple[str, str, str] | None:
    url = f'{EXPLORE_RAW_URL}/{topic}/{topic}.png'
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status != 200:
                return None
            with Image.open(BytesIO(response.read())) as img:
                resized = img.convert('RGBA').resize(ICON_SIZE, Image.Resampling.LANCZOS)
                buffer = BytesIO()
                resized.save(buffer, format='PNG', optimize=True)
                encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
                return (f'data:image/png;base64,{encoded}', f'{topic}.png', 'Original PNG')
    except urllib.error.HTTPError:
        return None
    except Exception as exc:
        logger.warning('Error processing GitHub Explore icon for %s: %s', topic, exc)
    return None


def resolve_icon_info(topic: str, brand_colors: dict[str, str]) -> tuple[str, str, str, str] | None:
    for provider, fn in (
        ('Custom', lambda t: _fetch_custom_svg(t, brand_colors)),
        ('Devicon', lambda t: _fetch_devicon_svg(t, brand_colors)),
        ('SimpleIcons', lambda t: _fetch_simple_icon_svg(t, brand_colors)),
        ('Explore', _fetch_explore_png),
    ):
        res = fn(topic)
        if res:
            return (provider, *res)
    return None
