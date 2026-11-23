from __future__ import annotations

from collections import defaultdict
import logging
import shutil
import urllib.parse

import yaml

from profile_sync.config import BADGES_DIR, CONFIG_PATH, GITHUB_WEB_URL
from profile_sync.github_client import collect_topics_map, fetch_metadata, get_username
from profile_sync.providers import build_pipeline, resolve_icon_info
from profile_sync.reporter import print_console_report, update_readme
from profile_sync.svg_builder import create_themed_badges

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def load_stack_config() -> tuple[set[str], dict[str, str], dict[str, list[str]]]:
    if not CONFIG_PATH.is_file():
        return set(), {}, {}
    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8')) or {}
    ignore = {str(t).lower() for t in raw.get('ignore', [])}
    aliases = {str(k).lower(): str(v) for k, v in (raw.get('aliases') or {}).items()}
    groups = {str(g): [str(t).lower() for t in items] for g, items in (raw.get('groups') or {}).items()}
    return ignore, aliases, groups


def process_badges(topic_repos: dict[str, list[str]], username: str, brand_colors: dict[str, str]) -> str:
    if BADGES_DIR.exists():
        shutil.rmtree(BADGES_DIR)
        logger.info('Cleaned badges directory: %s', BADGES_DIR)
    BADGES_DIR.mkdir(parents=True, exist_ok=True)

    ignore, aliases, groups = load_stack_config()
    topic_to_group = {t: grp for grp, items in groups.items() for t in items}
    fallback_group = list(groups.keys())[-1] if groups else 'Tools & Ecosystem'

    pipeline = build_pipeline()
    rendered_items: dict[str, str] = {}
    matched_records: list[dict] = []
    missing_icons: dict[str, list[str]] = {}
    total = len(topic_repos)

    for idx, (topic, repos) in enumerate(topic_repos.items(), start=1):
        low_topic = topic.lower()
        if low_topic in ignore:
            logger.info('[%d/%d] %-22s -> IGNORED', idx, total, topic)
            continue

        icon_res = resolve_icon_info(topic, brand_colors, pipeline)
        if not icon_res:
            missing_icons[topic] = repos
            logger.warning('[%d/%d] %-22s -> SKIPPED', idx, total, topic)
            continue

        label = aliases.get(low_topic, topic.replace('-', ' ')).upper()
        create_themed_badges(topic, icon_res.data_uri, icon_res.color, display_label=label)
        group_name = topic_to_group.get(low_topic, fallback_group)

        logger.info('[%d/%d] %-22s -> OK | %s | group=%s', idx, total, topic, icon_res.provider, group_name)
        matched_records.append(
            {
                'topic': topic,
                'provider': icon_res.provider,
                'source': icon_res.source_file,
                'color': icon_res.color,
                'count': len(repos),
            }
        )
        filter_url = f'{GITHUB_WEB_URL}/{username}?tab=repositories&topic={urllib.parse.quote(topic)}'
        rendered_items[low_topic] = (
            f'  <a href="{filter_url}">'
            f'<picture>'
            f'<source media="(prefers-color-scheme: dark)" srcset="assets/badges/{topic}-dark.svg">'
            f'<source media="(prefers-color-scheme: light)" srcset="assets/badges/{topic}-light.svg">'
            f'<img src="assets/badges/{topic}-light.svg" alt="{label}" vspace="4" hspace="3">'
            f'</picture>'
            f'</a>'
        )

    print_console_report(username, matched_records, missing_icons)

    grouped_blocks: dict[str, list[str]] = defaultdict(list)
    for grp, ordered_topics in groups.items():
        for t in ordered_topics:
            if t in rendered_items:
                grouped_blocks[grp].append(rendered_items.pop(t))

    for remaining_html in rendered_items.values():
        grouped_blocks[fallback_group].append(remaining_html)

    blocks = ['\n'.join(items) for items in grouped_blocks.values() if items]
    return '\n<br><br>\n'.join(blocks)


def main() -> None:
    username = get_username()
    brand_colors, _ = fetch_metadata()
    topic_repos = collect_topics_map(username)
    badges_html = process_badges(topic_repos, username, brand_colors)
    update_readme(badges_html)


if __name__ == '__main__':
    main()
