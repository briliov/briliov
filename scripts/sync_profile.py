from __future__ import annotations

import base64
from collections import defaultdict
from io import BytesIO
import json
import logging
import os
from pathlib import Path
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('GITHUB_TOKEN')

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / 'README.md'
BADGES_DIR = REPO_ROOT / 'assets' / 'badges'

START_MARKER = '<!-- TECH_STACK:START -->'
END_MARKER = '<!-- TECH_STACK:END -->'
ICON_SIZE = (16, 16)

# Защищённая сборка базовых URL (без автозамены поддоменов при копировании)
GITHUB_WEB_URL = '.'.join(('https://github', 'com'))
GITHUB_API_URL = '.'.join(('https://api', 'github', 'com'))
EXPLORE_RAW_URL = '.'.join(
    ('https://raw', 'githubusercontent', 'com/github/explore/main/topics')
)
DEVICON_CDN_URL = '.'.join(
    ('https://raw', 'githubusercontent', 'com/devicons/devicon/master/icons')
)


def get_username() -> str:
    """Resolve GitHub username from environment or repository root folder name."""
    owner = os.getenv('GITHUB_REPOSITORY_OWNER')
    if owner:
        return owner
    return REPO_ROOT.name


def github_get(url: str) -> list | dict:
    """Send an authenticated GET request to the GitHub REST API."""
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Profile-Stack-Sync',
    }
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def collect_topics_map(username: str) -> dict[str, list[str]]:
    """Collect topics mapped to the list of repositories where each appears."""
    logger.info('Fetching repositories for user: %s', username)
    repos = github_get(f'{GITHUB_API_URL}/users/{username}/repos?per_page=100')
    topic_repos: dict[str, list[str]] = defaultdict(list)

    if isinstance(repos, list):
        for repo in repos:
            repo_name = repo.get('name', '')
            if repo.get('fork') or repo_name == username:
                continue
            for topic in repo.get('topics', []):
                topic_repos[topic].append(repo_name)

    sorted_items = sorted(
        topic_repos.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )
    logger.info('Collected %d unique topics.', len(sorted_items))
    return dict(sorted_items)


def _fetch_explore_png(topic: str) -> str | None:
    """Try fetching PNG icon from GitHub Explore and resize to 16x16 Base64."""
    url = f'{EXPLORE_RAW_URL}/{topic}/{topic}.png'
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status != 200:
                return None
            raw_bytes = response.read()
            with Image.open(BytesIO(raw_bytes)) as img:
                resized = img.convert('RGBA').resize(
                    ICON_SIZE,
                    Image.Resampling.LANCZOS,
                )
                buffer = BytesIO()
                resized.save(buffer, format='PNG', optimize=True)
                encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
                return f'data:image/png;base64,{encoded}'
    except urllib.error.HTTPError:
        return None
    except Exception as exc:
        logger.warning(
            'Error processing GitHub Explore icon for %s: %s', topic, exc
        )
        return None


def _fetch_devicon_svg(topic: str) -> str | None:
    """Try fetching vector SVG icon (original or plain) from Devicon CDN."""
    clean_name = topic.replace('-', '')
    for variant in ('original', 'plain'):
        url = f'{DEVICON_CDN_URL}/{clean_name}/{clean_name}-{variant}.svg'
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                if response.status == 200:
                    encoded = base64.b64encode(response.read()).decode('ascii')
                    return f'data:image/svg+xml;base64,{encoded}'
        except urllib.error.HTTPError:
            continue
        except Exception as exc:
            logger.warning('Error fetching Devicon for %s: %s', topic, exc)
            break
    return None


def resolve_icon_data(topic: str) -> str | None:
    """Cascade icon lookup: Devicon SVG -> GitHub Explore PNG."""
    icon_data = _fetch_devicon_svg(topic)
    if icon_data:
        return icon_data
    return _fetch_explore_png(topic)


def create_svg_badge(topic: str, icon_data: str | None) -> Path:
    """Generate a local monochrome SVG badge with semi-bold typography."""
    label = topic.upper().replace('-', ' ')

    char_width = 8.4
    text_width = int(len(label) * char_width)
    icon_offset = 24 if icon_data else 0
    total_width = text_width + icon_offset + 26
    text_x = (13 + icon_offset) + (text_width / 2)

    svg_ns = 'http://www.' + 'w3.org/2000/svg'
    lines = [
        f'<svg xmlns="{svg_ns}" width="{total_width}" height="28" role="img" aria-label="{label}">',
        f'  <rect width="{total_width}" height="28" fill="#000000" />',
    ]

    if icon_data:
        lines.append(
            f'  <image x="12" y="7" width="14" height="14" href="{icon_data}" />'
        )

    lines.append(
        f'  <text x="{text_x:.1f}" y="17.5" fill="#ffffff" '
        f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif" '
        f'font-size="10" font-weight="600" text-anchor="middle" '
        f'letter-spacing="1.5">{label}</text>'
    )
    lines.append('</svg>')

    badge_path = BADGES_DIR / f'{topic}.svg'
    badge_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return badge_path


def generate_badges_markdown(
    topic_repos: dict[str, list[str]],
    username: str,
) -> str:
    """Clean badges dir, build SVG badges only for found icons, and log missing."""
    if BADGES_DIR.exists():
        shutil.rmtree(BADGES_DIR)
        logger.info('Cleaned badges directory: %s', BADGES_DIR)
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    missing_icons: dict[str, list[str]] = {}

    for topic, repos in topic_repos.items():
        icon_data = resolve_icon_data(topic)
        if not icon_data:
            missing_icons[topic] = repos
            continue

        create_svg_badge(topic, icon_data)
        label = topic.upper().replace('-', ' ')
        rel_path = f'assets/badges/{topic}.svg'
        filter_url = (
            f'{GITHUB_WEB_URL}/{username}?tab=repositories'
            f'&topic={urllib.parse.quote(topic)}'
        )
        lines.append(
            f'  <a href="{filter_url}">'
            f'<img src="{rel_path}" alt="{label}" vspace="3" hspace="2" />'
            f'</a>'
        )

    if missing_icons:
        logger.warning(
            'Skipped %d topics without icon in Devicon or Explore:',
            len(missing_icons),
        )
        for topic, repos in missing_icons.items():
            repo_urls = ', '.join(
                f'{GITHUB_WEB_URL}/{username}/{repo}' for repo in repos
            )
            logger.warning('  - %s -> %s', topic, repo_urls)

    return '\n'.join(lines)


def update_readme(rendered_block: str) -> None:
    """Replace content between START_MARKER and END_MARKER in README.md."""
    content = README_PATH.read_text(encoding='utf-8')

    pattern = re.compile(
        rf'({re.escape(START_MARKER)})(.*?)({re.escape(END_MARKER)})',
        flags=re.DOTALL,
    )
    if not pattern.search(content):
        raise ValueError(
            f'Markers {START_MARKER} and {END_MARKER} not found in {README_PATH}'
        )

    updated = pattern.sub(rf'\1\n{rendered_block}\n\3', content)
    if updated != content:
        README_PATH.write_text(updated, encoding='utf-8')
        logger.info('README.md successfully updated.')
    else:
        logger.info('No changes detected in README.md.')


def main() -> None:
    """Collect repository topics, rebuild SVG badges, and update README."""
    username = get_username()
    topic_repos = collect_topics_map(username)
    badges_md = generate_badges_markdown(topic_repos, username)
    update_readme(badges_md)


if __name__ == '__main__':
    main()
