from __future__ import annotations

from collections import defaultdict
import logging
import shutil
import urllib.parse

from profile_sync.config import BADGES_DIR, GITHUB_WEB_URL
from profile_sync.github_client import collect_topics_map, fetch_metadata, get_username
from profile_sync.providers import build_pipeline, resolve_icon_info
from profile_sync.reporter import print_console_report, update_readme
from profile_sync.svg_builder import create_svg_badge

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

GROUP_ORDER = ('Backend & Core', 'Frontend', 'Databases', 'DevOps & Cloud', 'Testing & Tools')


def process_badges(
    topic_repos: dict[str, list[str]],
    username: str,
    brand_colors: dict[str, str],
    auto_categories: dict[str, str],
) -> str:
    if BADGES_DIR.exists():
        shutil.rmtree(BADGES_DIR)
        logger.info('Cleaned badges directory: %s', BADGES_DIR)
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = build_pipeline()
    grouped_html: dict[str, list[str]] = defaultdict(list)
    matched_records: list[dict] = []
    missing_icons: dict[str, list[str]] = {}
    total = len(topic_repos)

    for idx, (topic, repos) in enumerate(topic_repos.items(), start=1):
        icon_res = resolve_icon_info(topic, brand_colors, pipeline)
        if not icon_res:
            missing_icons[topic] = repos
            logger.warning('[%d/%d] %-22s -> SKIPPED (no icon found)', idx, total, topic)
            continue

        create_svg_badge(topic, icon_res.data_uri)
        clean_name = topic.replace('-', '')
        category = auto_categories.get(clean_name, 'Testing & Tools')

        logger.info(
            '[%d/%d] %-22s -> OK | %s | color=%s | group=%s',
            idx, total, topic, icon_res.provider, icon_res.color, category,
        )
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
        grouped_html[category].append(
            f'  <a href="{filter_url}"><img src="{rel_path}" alt="{label}" vspace="3" hspace="2" /></a>'
        )

    print_console_report(username, matched_records, missing_icons)

    blocks = []
    for group in GROUP_ORDER:
        items = grouped_html.get(group)
        if items:
            blocks.append('\n'.join(items))
    return '\n<br>\n'.join(blocks)


def main() -> None:
    username = get_username()
    brand_colors, auto_categories = fetch_metadata()
    topic_repos = collect_topics_map(username)
    badges_html = process_badges(topic_repos, username, brand_colors, auto_categories)
    update_readme(badges_html)


if __name__ == '__main__':
    main()
