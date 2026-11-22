from __future__ import annotations

from collections import defaultdict
import json
import logging
import os
import urllib.request

from profile_sync.config import (
    DEVICON_META_URL,
    GITHUB_API_URL,
    REPO_ROOT,
    TOKEN,
)

logger = logging.getLogger(__name__)


def get_username() -> str:
    owner = os.getenv('GITHUB_REPOSITORY_OWNER')
    return owner if owner else REPO_ROOT.name


def github_get(url: str) -> list | dict:
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Profile-Stack-Sync',
    }
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def _apply_contrast_filter(hex_str: str) -> str:
    clean_hex = hex_str.lstrip('#')
    if len(clean_hex) == 6:
        r, g, b = (int(clean_hex[i : i + 2], 16) for i in (0, 2, 4))
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return f'#{clean_hex}' if luminance >= 75 else '#ffffff'
    return '#ffffff'


def fetch_devicon_colors() -> dict[str, str]:
    try:
        data = github_get(DEVICON_META_URL)
    except Exception as exc:
        logger.warning('Could not fetch devicon.json colors: %s', exc)
        return {}
    colors: dict[str, str] = {}
    if isinstance(data, list):
        for item in data:
            name = item.get('name', '')
            hex_color = item.get('color', '')
            if name and hex_color:
                colors[name] = _apply_contrast_filter(hex_color)
    return colors


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
    sorted_items = sorted(
        topic_repos.items(), key=lambda item: (-len(item), item)
    )
    logger.info('Collected %d unique topics.', len(sorted_items))
    return dict(sorted_items)
