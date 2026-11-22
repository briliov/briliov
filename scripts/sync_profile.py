from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.getenv('GITHUB_TOKEN')

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / 'README.md'
START_MARKER = '<!-- TECH_STACK:START -->'
END_MARKER = '<!-- TECH_STACK:END -->'


def get_username() -> str:
    """Resolve GitHub username from environment or repository root folder name."""
    owner = os.getenv('GITHUB_REPOSITORY_OWNER')
    if owner:
        return owner
    return Path(__file__).resolve().parent.parent.name


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


def collect_ranked_topics(username: str) -> list[str]:
    """Collect and sort topics by usage frequency across public repositories."""
    repos = github_get(
        f'https://api.github.com/users/{username}/repos?per_page=100'
    )
    counts: Counter[str] = Counter()

    if isinstance(repos, list):
        for repo in repos:
            if repo.get('fork') or repo.get('name') == username:
                continue
            for topic in repo.get('topics', []):
                counts[topic] += 1

    return sorted(counts.keys(), key=lambda t: (-counts[t], t))


def resolve_topic_icon(topic: str) -> str | None:
    """Return the official GitHub Explore icon URL if it exists, otherwise None."""
    icon_url = f'https://raw.githubusercontent.com/github/explore/main/topics/{topic}/{topic}.png'
    req = urllib.request.Request(icon_url, method='HEAD')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                return icon_url
    except urllib.error.HTTPError:
        pass
    return None


def render_topic_icons(topics: list[str], username: str) -> str:
    """Render clickable HTML icons for topics that have a valid image."""
    items = []
    for topic in topics:
        icon_url = resolve_topic_icon(topic)
        if not icon_url:
            continue

        filter_url = f'https://github.com/{username}?tab=repositories&topic={urllib.parse.quote(topic)}'
        items.append(
            f'  <a href="{filter_url}" title="{topic}">'
            f'<img src="{icon_url}" alt="{topic}" width="36" height="36" />'
            f'</a>'
        )

    return '\n'.join(items)


def update_readme(rendered_block: str) -> None:
    """Replace content between START_MARKER and END_MARKER in README.md."""
    with open(README_PATH, encoding='utf-8') as file:
        content = file.read()

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
        with open(README_PATH, 'w', encoding='utf-8') as file:
            file.write(updated)


def main() -> None:
    """Collect repository topics and update profile README icons."""
    topics = collect_ranked_topics(get_username())
    icons_html = render_topic_icons(topics, get_username())
    update_readme(icons_html)


if __name__ == '__main__':
    main()
