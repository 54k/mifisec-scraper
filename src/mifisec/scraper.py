"""Stage 1: Scrape course content into Obsidian vault."""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .utils import (
    BASE_URL, COURSES, GRAPH_CONFIG, SEMESTER_NAMES,
    get_discipline_tag, get_semester, sanitize, tags_yaml,
)


def get_course_structure(session: requests.Session, course_id: str) -> dict:
    resp = session.get(f"{BASE_URL}/api/course_home/outline/{course_id}")
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
    """Extract markdown content from xblock HTML page."""
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


def fetch_unit(session: requests.Session, block_id: str) -> str:
    try:
        resp = session.get(f"{BASE_URL}/xblock/{block_id}", timeout=30)
        resp.raise_for_status()
        return extract_content(resp.text)
    except requests.RequestException:
        return ""


def scrape_main_course(session: requests.Session, output_dir: Path, delay: float = 0.5):
    """Scrape the main MIFISEC course into semester-organized structure."""
    course = COURSES['main']
    print(f"Fetching structure: {course['name']}...")
    blocks = get_course_structure(session, course['id'])
    tree = build_tree(blocks)
    tree.sort(key=lambda ch: get_semester(ch['name']) + ch['name'])

    # Group by semester
    semesters = {}
    for ch_idx, chapter in enumerate(tree, 1):
        sem_id = get_semester(chapter['name'])
        semesters.setdefault(sem_id, []).append((ch_idx, chapter))

    total_units = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0

    for sem_id, chapters in semesters.items():
        sem_name = SEMESTER_NAMES[sem_id]
        sem_dir = output_dir / sem_name
        sem_dir.mkdir(parents=True, exist_ok=True)
        sem_tag = f'semester/{sem_id}' if sem_id != 'dpo' else 'track/dpo'

        sem_hub_lines = [
            '---', f'{tags_yaml([sem_tag, "type/semester-hub"])}',
            'aliases:', f'  - "{sem_name}"', '---', '',
            f'# {sem_name}', '', '> **nav:** [[index|← Программа]]', '',
        ]

        for ch_idx, chapter in chapters:
            ch_name_safe = sanitize(chapter['name'])
            disc_tag = get_discipline_tag(chapter['name'])
            ch_dir = sem_dir / f"{ch_idx:02d}. {ch_name_safe}"
            ch_dir.mkdir(parents=True, exist_ok=True)

            moc_name = sanitize(chapter['name'])
            moc_path = f"{sem_name}/{ch_idx:02d}. {ch_name_safe}/{moc_name}"
            sem_hub_lines.append(f"- [[{moc_path}|{chapter['name']}]]")

            moc_lines = [
                '---', f'{tags_yaml([sem_tag, disc_tag, "type/moc"])}',
                'aliases:', f'  - "{chapter["name"]}"', '---', '',
                f'> **nav:** [[{sem_name}/{sem_name}|← {sem_name}]]', '',
                f'# {chapter["name"]}', '',
            ]

            print(f"\n  [{sem_name}] {chapter['name']}")

            for sec_idx, section in enumerate(chapter['sections'], 1):
                sec_name_safe = sanitize(section['name'])
                sec_dir = ch_dir / f"{sec_idx:02d}. {sec_name_safe}"
                sec_dir.mkdir(parents=True, exist_ok=True)

                sec_rel = f"{sem_name}/{ch_idx:02d}. {ch_name_safe}/{sec_idx:02d}. {sec_name_safe}/{sec_name_safe}"
                moc_lines.append(f"- [[{sec_rel}|{section['name']}]]")

                sec_parts = [
                    '---', f'{tags_yaml([sem_tag, disc_tag, "type/module"])}',
                    'aliases:', f'  - "{section["name"]}"', '---', '',
                    f'> **nav:** [[{moc_path}|← {chapter["name"]}]]', '',
                    f'# {section["name"]}', '',
                ]

                for unit_idx, unit in enumerate(section['units'], 1):
                    processed += 1
                    unit_name_safe = sanitize(unit['name'])
                    print(f"    [{processed}/{total_units}] {unit['name']}...", end=' ', flush=True)

                    content = fetch_unit(session, unit['id'])
                    time.sleep(delay)

                    if content:
                        unit_nav = sec_rel
                        unit_file = sec_dir / f"{unit_idx:02d}. {unit_name_safe}.md"
                        unit_file.write_text(
                            f'---\n{tags_yaml([sem_tag, disc_tag, "type/lesson"])}\n---\n\n'
                            f'> **nav:** [[{unit_nav}|← {section["name"]}]]\n\n'
                            f'# {unit["name"]}\n\n{content}\n',
                            encoding='utf-8'
                        )
                        sec_parts.extend([f"## {unit['name']}", "", content, ""])
                        print(f"OK ({len(content)})")
                    else:
                        print("EMPTY")

                (sec_dir / f"{sec_name_safe}.md").write_text('\n'.join(sec_parts), encoding='utf-8')

            moc_lines.append("")
            (ch_dir / f"{moc_name}.md").write_text('\n'.join(moc_lines), encoding='utf-8')

        sem_hub_lines.append("")
        (sem_dir / f"{sem_name}.md").write_text('\n'.join(sem_hub_lines), encoding='utf-8')


def scrape_track(session: requests.Session, output_dir: Path, track_key: str, delay: float = 0.5):
    """Scrape a track course (pentest/compliance)."""
    track = COURSES[track_key]
    track_name = track['name']
    track_tag = track.get('tag', f'track/{track_key}')
    track_dir = output_dir / track_name
    track_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nFetching structure: {track_name}...")
    try:
        blocks = get_course_structure(session, track['id'])
        tree = build_tree(blocks)
    except Exception as e:
        print(f"  Error: {e}")
        tree = []

    if not tree:
        (track_dir / f"{track_name}.md").write_text(
            f'---\n{tags_yaml([track_tag, "type/track-hub"])}\n---\n\n'
            f'# {track_name}\n\n> **nav:** [[index|← Программа]]\n\n'
            f'*Курс пустой или недоступен*\n', encoding='utf-8')
        return

    total = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0

    hub_lines = [
        '---', f'{tags_yaml([track_tag, "type/track-hub"])}',
        'aliases:', f'  - "{track_name}"', '---', '',
        f'# {track_name}', '', '> **nav:** [[index|← Программа]]', '',
    ]

    for ch_idx, chapter in enumerate(tree, 1):
        ch_safe = sanitize(chapter['name'])
        ch_dir = track_dir / f"{ch_idx:02d}. {ch_safe}"
        ch_dir.mkdir(parents=True, exist_ok=True)
        hub_lines.extend([f"## {chapter['name']}", ""])
        print(f"  {chapter['name']}")

        for sec_idx, section in enumerate(chapter['sections'], 1):
            sec_safe = sanitize(section['name'])
            sec_rel = f"{track_name}/{ch_idx:02d}. {ch_safe}/{sec_safe}"
            hub_lines.append(f"- [[{sec_rel}|{section['name']}]]")

            sec_parts = [
                '---', f'{tags_yaml([track_tag, "type/module"])}',
                'aliases:', f'  - "{section["name"]}"', '---', '',
                f'> **nav:** [[{track_name}/{track_name}|← {track_name}]]', '',
                f'# {section["name"]}', '',
            ]

            for unit_idx, unit in enumerate(section['units'], 1):
                processed += 1
                unit_safe = sanitize(unit['name'])
                print(f"    [{processed}/{total}] {unit['name']}...", end=' ', flush=True)

                content = fetch_unit(session, unit['id'])
                time.sleep(delay)

                if content:
                    unit_file = ch_dir / f"{sec_idx:02d}-{unit_idx:02d}. {unit_safe}.md"
                    unit_file.write_text(
                        f'---\n{tags_yaml([track_tag, "type/lesson"])}\n---\n\n'
                        f'> **nav:** [[{sec_rel}|← {section["name"]}]]\n\n'
                        f'# {unit["name"]}\n\n{content}\n', encoding='utf-8')
                    sec_parts.extend([f"## {unit['name']}", "", content, ""])
                    print(f"OK ({len(content)})")
                else:
                    print("EMPTY")

            (ch_dir / f"{sec_safe}.md").write_text('\n'.join(sec_parts), encoding='utf-8')
        hub_lines.append("")

    (track_dir / f"{track_name}.md").write_text('\n'.join(hub_lines), encoding='utf-8')
    print(f"  Done: {processed} units")


def write_index(output_dir: Path):
    """Write index.md and .obsidian/graph.json."""
    index = [
        '---', f'{tags_yaml(["type/index"])}',
        'aliases:', '  - MIFISEC', '  - Безопасность информационных систем', '---', '',
        '# Безопасность информационных систем', '',
        'Магистратура НИЯУ МИФИ x SkillFactory', '',
        '## Структура программы', '',
    ]
    for sem_id in ['1', '2', '3', '4', 'dpo']:
        sem_name = SEMESTER_NAMES[sem_id]
        if (output_dir / sem_name).exists():
            index.append(f'- [[{sem_name}/{sem_name}|{sem_name}]]')
    index.extend(['', '## Треки', ''])
    for key in ['pentest', 'compliance']:
        track_name = COURSES[key]['name']
        index.append(f'- [[{track_name}/{track_name}|{track_name}]]')
    index.append('')
    (output_dir / 'index.md').write_text('\n'.join(index), encoding='utf-8')

    obsidian_dir = output_dir / '.obsidian'
    obsidian_dir.mkdir(exist_ok=True)
    (obsidian_dir / 'graph.json').write_text(json.dumps(GRAPH_CONFIG, indent=2), encoding='utf-8')
