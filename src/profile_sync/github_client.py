from __future__ import annotations

from collections import defaultdict
import colorsys
import json
import logging
import os
import re
import time
import urllib.parse
import urllib.request

import yaml

from profile_sync.config import DEVICON_META_URL, GITHUB_API_URL, LINGUIST_URL, REPO_ROOT, TOKEN

logger = logging.getLogger(__name__)
SIMPLE_ICONS_META_URLS = (
    '.'.join(('https://raw', 'githubusercontent', 'com/simple-icons/simple-icons/develop/data/simple-icons.json')),
    '.'.join(('https://raw', 'githubusercontent', 'com/simple-icons/simple-icons/develop/_data/simple-icons.json')),
)

DESC_RULES = (
    (('database', 'sql', 'orm', 'relational'), 'Databases'),
    (('css', 'html', 'frontend', 'front-end', 'markup', 'ui ', 'stylesheet'), 'Frontend & Markup'),
    (('container', 'deploy', 'server', 'ci/cd', 'continuous integration', 'shell', 'cloud', 'proxy'), 'DevOps & Cloud'),
    (('framework', 'backend', 'back-end', 'http', 'validation', 'programming language', 'runtime'), 'Backend & Core'),
)


def get_username() -> str:
    owner = os.getenv('GITHUB_REPOSITORY_OWNER')
    return owner if owner else REPO_ROOT.name


def github_get(url: str) -> list | dict:
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'Profile-Stack-Sync'}
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def _boost_dark_color(hex_str: str) -> str:
    clean_hex = hex_str.lstrip('#')
    if len(clean_hex) != 6:
        return '#ffffff'

    r, g, b = (int(clean_hex[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)

    if s < 0.12 and l < 0.65:
        return '#ffffff'
    if l < 0.65:
        l = 0.68

    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return f'#{int(nr * 255):02x}{int(ng * 255):02x}{int(nb * 255):02x}'


def fetch_linguist_categories() -> dict[str, str]:
    categories: dict[str, str] = {}
    try:
        with urllib.request.urlopen(LINGUIST_URL, timeout=20) as response:
            data = yaml.safe_load(response.read().decode('utf-8'))
    except Exception as exc:
        logger.warning('Could not fetch Linguist languages.yml: %s', exc)
        return categories

    if not isinstance(data, dict):
        return categories

    for lang_name, meta in data.items():
        if not isinstance(meta, dict):
            continue
        low = lang_name.lower()
        if low in ('django', 'jinja', 'liquid'):
            continue
        lang_type = meta.get('type', '')
        lang_group = meta.get('group', '')

        if low in ('sql', 'plpgsql', 'tsql'):
            category = 'Databases'
        elif lang_group == 'Shell' or low == 'dockerfile':
            category = 'DevOps & Cloud'
        elif lang_type == 'markup':
            category = 'Frontend & Markup'
        elif lang_type == 'programming':
            category = 'Backend & Core'
        else:
            continue

        for key in [lang_name] + meta.get('aliases', []):
            slug = re.sub(r'[^a-z0-9]', '', str(key).lower())
            if slug:
                categories[slug] = category

    return categories


def classify_topic_via_github(topic: str, linguist_map: dict[str, str]) -> tuple[bool, str]:
    """Return (is_valid_tech, category) using GitHub Topics API + Linguist."""
    clean = topic.replace('-', '')
    base_cat = linguist_map.get(clean)

    try:
        q = urllib.parse.quote(topic)
        res = github_get(f'{GITHUB_API_URL}/search/topics?q={q}')
        items = res.get('items', []) if isinstance(res, dict) else []
        match = next((i for i in items if i.get('name', '').lower() == topic.lower()), None)

        if match:
            if not match.get('curated', False) and not base_cat:
                return False, ''
            if base_cat:
                return True, base_cat
            desc = (match.get('short_description') or match.get('description') or '').lower()
            for keywords, group in DESC_RULES:
                if any(kw in desc for kw in keywords):
                    return True, group
            return True, 'Tools & API'
    except Exception as exc:
        logger.debug('Topic search fallback for %s: %s', topic, exc)

    return True, base_cat or 'Tools & API'


def fetch_metadata() -> tuple[dict[str, str], dict[str, str]]:
    colors: dict[str, str] = {}
    for meta_url in SIMPLE_ICONS_META_URLS:
        try:
            si_data = github_get(meta_url)
            icons_list = si_data.get('icons', []) if isinstance(si_data, dict) else si_data
            if isinstance(icons_list, list) and icons_list:
                for item in icons_list:
                    slug = re.sub(r'[^a-z0-9]', '', item.get('title', '').lower())
                    hex_color = item.get('hex', '')
                    if slug and hex_color:
                        colors[slug] = _boost_dark_color(hex_color)
                break
        except Exception:
            continue

    try:
        dev_data = github_get(DEVICON_META_URL)
        if isinstance(dev_data, list):
            for item in dev_data:
                name = item.get('name', '')
                hex_color = item.get('color', '')
                if name and hex_color:
                    colors[name] = _boost_dark_color(hex_color)
    except Exception as exc:
        logger.warning('Could not fetch devicon.json colors: %s', exc)

    return colors, fetch_linguist_categories()


def collect_topics_map(username: str) -> dict[str, list[str]]:
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
    sorted_items = sorted(topic_repos.items(), key=lambda item: (-len(item), item))
    logger.info('Collected %d unique topics.', len(sorted_items))
    return dict(sorted_items)
