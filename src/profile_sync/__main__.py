from __future__ import annotations

import logging
import shutil
import urllib.parse

from profile_sync.config import BADGES_DIR, GITHUB_WEB_URL
from profile_sync.github_client import collect_topics_map, fetch_devicon_colors, get_username
from profile_sync.providers import build_pipeline, resolve_icon_info
from profile_sync.reporter import print_console_report, update_readme
from profile_sync.svg_builder import create_svg_badge

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def process_badges(topic_repos: dict[str, list[str]], username: str, brand_colors: dict[str, str]) -> str:
    if BADGES_DIR.exists():
        shutil.rmtree(BADGES_DIR)
        logger.info('Cleaned badges directory: %s', BADGES_DIR)
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = build_pipeline()
    html_lines = []
    matched_records: list[dict] = []
    missing_icons: dict[str, list[str]] = {}

    for topic, repos in topic_repos.items():
        icon_res = resolve_icon_info(topic, brand_colors, pipeline)
        if not icon_res:
            missing_icons[topic] = repos
            continue
        create_svg_badge(topic, icon_res.data_uri)
        matched_records.append(
            {
                'topic': topic,
                'provider': icon_res.provider,
                'source': icon_res.source_file,
                'color': icon_res.color,
                'count': len(repos),
            }
        )
        label = topic.upper().replace('-', ' ')
        rel_path = f'assets/badges/{topic}.svg'
        filter_url = f'{GITHUB_WEB_URL}/{username}?tab=repositories&topic={urllib.parse.quote(topic)}'
        html_lines.append(f'  <a href="{filter_url}"><img src="{rel_path}" alt="{label}" vspace="3" hspace="2" /></a>')

    print_console_report(username, matched_records, missing_icons)
    return '\n'.join(html_lines)


def main() -> None:
    username = get_username()
    brand_colors = fetch_devicon_colors()
    topic_repos = collect_topics_map(username)
    badges_html = process_badges(topic_repos, username, brand_colors)
    update_readme(badges_html)


if __name__ == '__main__':
    main()
