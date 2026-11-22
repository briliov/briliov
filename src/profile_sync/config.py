from __future__ import annotations
import os
from pathlib import Path

TOKEN = os.getenv('GITHUB_TOKEN')
REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / 'README.md'
BADGES_DIR = REPO_ROOT / 'assets' / 'badges'
CUSTOM_ICONS_DIR = REPO_ROOT / 'assets' / 'custom_icons'

START_MARKER = '<!-- TECH_STACK:START -->'
END_MARKER = '<!-- TECH_STACK:END -->'
ICON_SIZE = (16, 16)

GITHUB_WEB_URL = '.'.join(('https://github', 'com'))
GITHUB_API_URL = '.'.join(('https://api', 'github', 'com'))
EXPLORE_RAW_URL = '.'.join(('https://raw', 'githubusercontent', 'com/github/explore/main/topics'))
DEVICON_CDN_URL = '.'.join(('https://raw', 'githubusercontent', 'com/devicons/devicon/master/icons'))
DEVICON_META_URL = '.'.join(('https://raw', 'githubusercontent', 'com/devicons/devicon/master/devicon.json'))
SIMPLE_ICONS_URL = '.'.join(('https://raw', 'githubusercontent', 'com/simple-icons/simple-icons/develop/icons'))

PROVIDER_ORDER = ('Custom', 'Devicon', 'SimpleIcons', 'Explore')
