#!/usr/bin/env python3
"""
SkillFactory MIFISEC Course Scraper → Obsidian Vault

Скачивает курс "Безопасность информационных систем" (МИФИ) и треки
и создаёт готовый Obsidian vault со структурой:

  vault/
  ├── index.md
  ├── Семестр 1/  (хаб + дисциплины)
  ├── Семестр 2/
  ├── Семестр 3/
  ├── Семестр 4/
  ├── ДПО и факультативы/
  ├── Трек Пентест/
  └── Трек Комплаенс/

Использование:
  1. pip install requests beautifulsoup4 markdownify
  2. Положить cookies.json рядом (см. инструкцию ниже)
  3. python3 scrape.py
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# === CONFIG ===
BASE_URL = "https://lms.skillfactory.ru"
OUTPUT_DIR = Path(__file__).parent / "vault"
COOKIES_FILE = Path(__file__).parent / "cookies.json"
DELAY = 0.5  # seconds between requests

COURSES = {
    "main": {
        "id": "course-v1:SkillFactory+MIFISEC+SEP_2023",
        "name": "Безопасность информационных систем",
    },
    "pentest": {
        "id": "course-v1:SkillFactory+mifisec_pentest2023+FEB_2024",
        "name": "Трек Пентест",
        "tag": "track/pentest",
    },
    "compliance": {
        "id": "course-v1:SkillFactory+mifisec_compliance2023+FEB_2024",
        "name": "Трек Комплаенс",
        "tag": "track/compliance",
    },
}

# Semester assignment by chapter name prefix
SEMESTER_PATTERNS = [
    (r'^I\.', '1'),
    (r'^II\.', '2'),
    (r'^III[\.\-]', '3'),
    (r'^IV\.', '4'),
]

SEMESTER_NAMES = {
    '1': 'Семестр 1',
    '2': 'Семестр 2',
    '3': 'Семестр 3',
    '4': 'Семестр 4',
    'dpo': 'ДПО и факультативы',
}

# Discipline → tag mapping
DISCIPLINE_TAGS = {
    'Криптография': 'discipline/crypto',
    'Сети и системы': 'discipline/networks',
    'Защита в операционных системах': 'discipline/os-security',
    'Программная инженерия': 'discipline/programming',
    'Теоретические основы ИБ': 'discipline/theory',
    'Защищенные информационные системы': 'discipline/secure-systems',
    'Нормативно-правовое': 'discipline/compliance',
    'Технические средства защиты': 'discipline/tech-tools',
    'Разработка защищенных': 'discipline/secure-dev',
    'Управление информационной безопасностью': 'discipline/isms',
    'Мониторинг, аналитика': 'discipline/monitoring',
    'Технология построения защищенных': 'discipline/secure-architecture',
    'Социальная инженерия': 'discipline/social-engineering',
    'Формализованные модели': 'discipline/formal-models',
    'Искусственный интеллект': 'discipline/ai-security',
    'Компьютерная криминалистика': 'discipline/forensics',
    'Форензика': 'discipline/forensics',
    'Аттестация, сертификация': 'discipline/certification',
    'АСУ ТП': 'discipline/ics-security',
    'Адаптационный': 'type/intro',
    'блокчейн': 'discipline/blockchain',
}

GRAPH_CONFIG = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,
    "showAttachments": False,
    "hideUnresolved": False,
    "showOrphans": False,
    "collapse-color-groups": False,
    "colorGroups": [
        {"query": "path:index", "color": {"a": 1, "rgb": 16711680}},
        {"query": "tag:#type/semester-hub", "color": {"a": 1, "rgb": 16766720}},
        {"query": "tag:#type/track-hub", "color": {"a": 1, "rgb": 16711935}},
        {"query": "tag:#type/moc", "color": {"a": 1, "rgb": 16776960}},
        {"query": "tag:#semester/1", "color": {"a": 1, "rgb": 4495783}},
        {"query": "tag:#semester/2", "color": {"a": 1, "rgb": 3329330}},
        {"query": "tag:#semester/3", "color": {"a": 1, "rgb": 16744448}},
        {"query": "tag:#semester/4", "color": {"a": 1, "rgb": 16729156}},
        {"query": "tag:#track/dpo", "color": {"a": 1, "rgb": 10494192}},
        {"query": "tag:#type/org", "color": {"a": 0.4, "rgb": 6710886}},
    ],
    "collapse-display": False,
    "showArrow": True,
    "textFadeMultiplier": -3,
    "nodeSizeMultiplier": 2.5,
    "lineSizeMultiplier": 0.5,
    "collapse-forces": False,
    "centerStrength": 0.25,
    "repelStrength": 18,
    "linkStrength": 0.8,
    "linkDistance": 120,
    "scale": 0.4,
    "close": False,
}


# === HELPERS ===

def load_cookies() -> dict:
    if not COOKIES_FILE.exists():
        print("ERROR: cookies.json not found!")
        print()
        print("Инструкция:")
        print("1. Залогинься на https://student-lk.skillfactory.ru/my-study")
        print("2. Открой DevTools (F12) → Application → Cookies → skillfactory.ru")
        print("3. Создай cookies.json:")
        print()
        print('  {')
        print('    "sessionid": "...",')
        print('    "edx-jwt-cookie-header-payload": "...",')
        print('    "edx-jwt-cookie-signature": "..."')
        print('  }')
        print()
        print("Или экспортируй через Cookie-Editor (поддерживается массив)")
        raise SystemExit(1)

    with open(COOKIES_FILE, 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        cookies = {}
        for c in data:
            name = c.get('name', '')
            if name in ('sessionid', 'edx-jwt-cookie-header-payload', 'edx-jwt-cookie-signature'):
                cookies[name] = c['value']
        return cookies
    return data


def sanitize(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len]


def get_semester(chapter_name: str) -> str:
    for pattern, sem_id in SEMESTER_PATTERNS:
        if re.search(pattern, chapter_name):
            return sem_id
    return 'dpo'


def get_discipline_tag(chapter_name: str) -> str:
    for pattern, tag in DISCIPLINE_TAGS.items():
        if pattern.lower() in chapter_name.lower():
            return tag
    return 'discipline/other'


def tags_yaml(tags: list[str]) -> str:
    lines = ['tags:']
    for t in tags:
        lines.append(f'  - {t}')
    return '\n'.join(lines)


# === SCRAPING ===

session = requests.Session()


def init_session():
    session.cookies.update(load_cookies())
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })


def get_course_structure(course_id: str) -> dict:
    url = f"{BASE_URL}/api/course_home/outline/{course_id}"
    resp = session.get(url)
    resp.raise_for_status()
    return resp.json()['course_blocks']['blocks']


def build_tree(blocks: dict) -> list[dict]:
    course_block = next((b for b in blocks.values() if b.get('type') == 'course'), None)
    if not course_block:
        return []
    tree = []
    for ch_id in course_block.get('children', []):
        ch = blocks.get(ch_id, {})
        chapter = {'id': ch_id, 'name': ch.get('display_name', '?'), 'sections': []}
        for seq_id in ch.get('children', []):
            seq = blocks.get(seq_id, {})
            section = {'id': seq_id, 'name': seq.get('display_name', '?'), 'units': []}
            for vert_id in seq.get('children', []):
                vert = blocks.get(vert_id, {})
                section['units'].append({'id': vert_id, 'name': vert.get('display_name', '?')})
            chapter['sections'].append(section)
        tree.append(chapter)
    return tree


def extract_content(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    parts = []
    for xb in soup.find_all('div', class_='xblock', attrs={'data-block-type': True}):
        bt = xb.get('data-block-type', '')
        if bt == 'html':
            if len(xb.get_text(strip=True)) < 10:
                continue
            for tag in xb.find_all(['script', 'style', 'link']):
                tag.decompose()
            for div in xb.find_all('div', class_=re.compile(r'^h[1-6]$')):
                level = (div.get('class') or ['h2'])[0]
                new_tag = soup.new_tag(level)
                new_tag.string = div.get_text()
                div.replace_with(new_tag)
            content_div = xb.find('div', class_='main-block') or xb
            html_content = re.sub(r'src="//lms-cdn', 'src="https://lms-cdn', str(content_div))
            markdown = md(html_content, heading_style='atx', bullets='-', strip=['script', 'style', 'link'])
            markdown = re.sub(r'\n{3,}', '\n\n', markdown).strip()
            if markdown:
                parts.append(markdown)
        elif bt == 'video':
            video_div = xb.find('div', attrs={'data-metadata': True})
            if video_div:
                try:
                    meta = json.loads(str(video_div.get('data-metadata', '{}')))
                    sources = meta.get('sources', [])
                    if sources:
                        parts.append(f"\n> [!video] Видео\n> {sources[0]}\n")
                except (json.JSONDecodeError, TypeError):
                    pass
    return '\n\n---\n\n'.join(parts)


def fetch_unit(block_id: str) -> str:
    try:
        resp = session.get(f"{BASE_URL}/xblock/{block_id}", timeout=30)
        resp.raise_for_status()
        return extract_content(resp.text)
    except requests.RequestException:
        return ""


# === VAULT BUILDING ===

def scrape_main_course():
    """Scrape the main MIFISEC course into semester-organized structure."""
    course = COURSES['main']
    print(f"Fetching structure: {course['name']}...")
    blocks = get_course_structure(course['id'])
    tree = build_tree(blocks)
    tree.sort(key=lambda ch: get_semester(ch['name']) + ch['name'])

    print(f"  {len(tree)} chapters")

    # Group chapters by semester
    semesters = {}
    for ch_idx, chapter in enumerate(tree, 1):
        sem_id = get_semester(chapter['name'])
        if sem_id not in semesters:
            semesters[sem_id] = []
        semesters[sem_id].append((ch_idx, chapter))

    total_units = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0

    for sem_id, chapters in semesters.items():
        sem_name = SEMESTER_NAMES[sem_id]
        sem_dir = OUTPUT_DIR / sem_name
        sem_dir.mkdir(parents=True, exist_ok=True)
        sem_tag = f'semester/{sem_id}' if sem_id != 'dpo' else 'track/dpo'

        # Semester hub
        sem_hub_lines = [
            '---',
            f'{tags_yaml([sem_tag, "type/semester-hub"])}',
            f'aliases:',
            f'  - "{sem_name}"',
            '---',
            '',
            f'# {sem_name}',
            '',
            '> **nav:** [[index|← Программа]]',
            '',
        ]

        for ch_idx, chapter in chapters:
            ch_name_clean = re.sub(r'^[IVX]+[\.\-]\s*', '', chapter['name']).strip()
            ch_name_safe = sanitize(chapter['name'])
            disc_tag = get_discipline_tag(chapter['name'])
            ch_dir = sem_dir / f"{ch_idx:02d}. {ch_name_safe}"
            ch_dir.mkdir(parents=True, exist_ok=True)

            # MOC file (named after discipline)
            moc_name = sanitize(chapter['name'])
            moc_path = f"{sem_name}/{ch_idx:02d}. {ch_name_safe}/{moc_name}"
            sem_hub_lines.append(f"- [[{moc_path}|{chapter['name']}]]")

            moc_lines = [
                '---',
                f'{tags_yaml([sem_tag, disc_tag, "type/moc"])}',
                f'aliases:',
                f'  - "{chapter["name"]}"',
                '---',
                '',
                f'> **nav:** [[{sem_name}/{sem_name}|← {sem_name}]]',
                '',
                f'# {chapter["name"]}',
                '',
            ]

            print(f"\n  [{sem_name}] {chapter['name']}")

            for sec_idx, section in enumerate(chapter['sections'], 1):
                sec_name_safe = sanitize(section['name'])
                sec_dir = ch_dir / f"{sec_idx:02d}. {sec_name_safe}"
                sec_dir.mkdir(parents=True, exist_ok=True)

                sec_rel = f"{sem_name}/{ch_idx:02d}. {ch_name_safe}/{sec_idx:02d}. {sec_name_safe}/{sec_name_safe}"
                moc_lines.append(f"- [[{sec_rel}|{section['name']}]]")

                # Section aggregate file
                sec_parts = [
                    '---',
                    f'{tags_yaml([sem_tag, disc_tag, "type/module"])}',
                    f'aliases:',
                    f'  - "{section["name"]}"',
                    '---',
                    '',
                    f'> **nav:** [[{moc_path}|← {chapter["name"]}]]',
                    '',
                    f'# {section["name"]}',
                    '',
                ]

                for unit_idx, unit in enumerate(section['units'], 1):
                    processed += 1
                    unit_name_safe = sanitize(unit['name'])
                    print(f"    [{processed}/{total_units}] {unit['name']}...", end=' ', flush=True)

                    content = fetch_unit(unit['id'])
                    time.sleep(DELAY)

                    if content:
                        # Unit file
                        unit_file = sec_dir / f"{unit_idx:02d}. {unit_name_safe}.md"
                        unit_nav = f"{sem_name}/{ch_idx:02d}. {ch_name_safe}/{sec_idx:02d}. {sec_name_safe}/{sec_name_safe}"
                        unit_file.write_text(
                            f'---\n'
                            f'{tags_yaml([sem_tag, disc_tag, "type/lesson"])}\n'
                            f'---\n\n'
                            f'> **nav:** [[{unit_nav}|← {section["name"]}]]\n\n'
                            f'# {unit["name"]}\n\n'
                            f'{content}\n',
                            encoding='utf-8'
                        )
                        sec_parts.append(f"## {unit['name']}")
                        sec_parts.append("")
                        sec_parts.append(content)
                        sec_parts.append("")
                        print(f"OK ({len(content)})")
                    else:
                        print("EMPTY")

                # Write section file
                sec_file = sec_dir / f"{sec_name_safe}.md"
                sec_file.write_text('\n'.join(sec_parts), encoding='utf-8')

            moc_lines.append("")
            # Write MOC
            (ch_dir / f"{moc_name}.md").write_text('\n'.join(moc_lines), encoding='utf-8')

        sem_hub_lines.append("")
        (sem_dir / f"{sem_name}.md").write_text('\n'.join(sem_hub_lines), encoding='utf-8')

    return semesters


def scrape_track(track_key: str):
    """Scrape a track course (pentest/compliance)."""
    track = COURSES[track_key]
    track_name = track['name']
    track_tag = track.get('tag', f'track/{track_key}')
    track_dir = OUTPUT_DIR / track_name
    track_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nFetching structure: {track_name}...")
    try:
        blocks = get_course_structure(track['id'])
        tree = build_tree(blocks)
    except Exception as e:
        print(f"  Error: {e}")
        tree = []

    if not tree:
        print(f"  Empty course, creating placeholder")
        (track_dir / f"{track_name}.md").write_text(
            f'---\n{tags_yaml([track_tag, "type/track-hub"])}\n---\n\n'
            f'# {track_name}\n\n> **nav:** [[index|← Программа]]\n\n'
            f'*Курс пустой или недоступен*\n',
            encoding='utf-8'
        )
        return

    total = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0

    hub_lines = [
        '---',
        f'{tags_yaml([track_tag, "type/track-hub"])}',
        'aliases:',
        f'  - "{track_name}"',
        '---',
        '',
        f'# {track_name}',
        '',
        '> **nav:** [[index|← Программа]]',
        '',
    ]

    for ch_idx, chapter in enumerate(tree, 1):
        ch_safe = sanitize(chapter['name'])
        ch_dir = track_dir / f"{ch_idx:02d}. {ch_safe}"
        ch_dir.mkdir(parents=True, exist_ok=True)

        hub_lines.append(f"## {chapter['name']}")
        hub_lines.append("")
        print(f"  {chapter['name']}")

        for sec_idx, section in enumerate(chapter['sections'], 1):
            sec_safe = sanitize(section['name'])
            sec_rel = f"{track_name}/{ch_idx:02d}. {ch_safe}/{sec_safe}"
            hub_lines.append(f"- [[{sec_rel}|{section['name']}]]")

            sec_parts = [
                '---',
                f'{tags_yaml([track_tag, "type/module"])}',
                f'aliases:',
                f'  - "{section["name"]}"',
                '---',
                '',
                f'> **nav:** [[{track_name}/{track_name}|← {track_name}]]',
                '',
                f'# {section["name"]}',
                '',
            ]

            for unit_idx, unit in enumerate(section['units'], 1):
                processed += 1
                unit_safe = sanitize(unit['name'])
                print(f"    [{processed}/{total}] {unit['name']}...", end=' ', flush=True)

                content = fetch_unit(unit['id'])
                time.sleep(DELAY)

                if content:
                    unit_file = ch_dir / f"{sec_idx:02d}-{unit_idx:02d}. {unit_safe}.md"
                    unit_file.write_text(
                        f'---\n{tags_yaml([track_tag, "type/lesson"])}\n---\n\n'
                        f'> **nav:** [[{sec_rel}|← {section["name"]}]]\n\n'
                        f'# {unit["name"]}\n\n{content}\n',
                        encoding='utf-8'
                    )
                    sec_parts.append(f"## {unit['name']}")
                    sec_parts.append("")
                    sec_parts.append(content)
                    sec_parts.append("")
                    print(f"OK ({len(content)})")
                else:
                    print("EMPTY")

            (ch_dir / f"{sec_safe}.md").write_text('\n'.join(sec_parts), encoding='utf-8')

        hub_lines.append("")

    (track_dir / f"{track_name}.md").write_text('\n'.join(hub_lines), encoding='utf-8')
    print(f"  Done: {processed} units")


def write_index():
    """Write index.md and .obsidian/graph.json."""
    index = [
        '---',
        f'{tags_yaml(["type/index"])}',
        'aliases:',
        '  - MIFISEC',
        '  - Безопасность информационных систем',
        '---',
        '',
        '# Безопасность информационных систем',
        '',
        'Магистратура НИЯУ МИФИ x SkillFactory',
        '',
        '## Структура программы',
        '',
    ]
    for sem_id in ['1', '2', '3', '4', 'dpo']:
        sem_name = SEMESTER_NAMES[sem_id]
        sem_path = f"{sem_name}/{sem_name}"
        if (OUTPUT_DIR / sem_name).exists():
            index.append(f'- [[{sem_path}|{sem_name}]]')
    index.extend(['', '## Треки', ''])
    for key in ['pentest', 'compliance']:
        track_name = COURSES[key]['name']
        index.append(f'- [[{track_name}/{track_name}|{track_name}]]')
    index.append('')

    (OUTPUT_DIR / 'index.md').write_text('\n'.join(index), encoding='utf-8')

    # Graph config
    obsidian_dir = OUTPUT_DIR / '.obsidian'
    obsidian_dir.mkdir(exist_ok=True)
    (obsidian_dir / 'graph.json').write_text(json.dumps(GRAPH_CONFIG, indent=2), encoding='utf-8')


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    init_session()

    scrape_main_course()
    scrape_track('pentest')
    scrape_track('compliance')
    write_index()

    print(f"\n{'='*60}")
    print(f"DONE! Vault: {OUTPUT_DIR}")
    print(f"Open in Obsidian: File → Open Vault → {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
