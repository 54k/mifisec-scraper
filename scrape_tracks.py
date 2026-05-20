#!/usr/bin/env python3
"""Scrape pentest and compliance tracks into vault."""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

BASE_URL = "https://lms.skillfactory.ru"
VAULT = Path(__file__).parent / "vault"
DELAY = 0.5

TRACKS = {
    "course-v1:SkillFactory+mifisec_pentest2023+FEB_2024": {
        "name": "Трек Пентест",
        "tag": "track/pentest",
        "dir": "Трек Пентест",
    },
    "course-v1:SkillFactory+mifisec_compliance2023+FEB_2024": {
        "name": "Трек Комплаенс",
        "tag": "track/compliance",
        "dir": "Трек Комплаенс",
    },
}

COOKIES_FILE = Path(__file__).parent / "cookies.json"


def load_cookies():
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


session = requests.Session()
session.cookies.update(load_cookies())
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
})


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:80]


def get_course_structure(course_id):
    url = f"{BASE_URL}/api/course_home/outline/{course_id}"
    resp = session.get(url)
    resp.raise_for_status()
    return resp.json()['course_blocks']['blocks']


def extract_content(html):
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    xblocks = soup.find_all('div', class_='xblock', attrs={'data-block-type': True})
    for xb in xblocks:
        bt = xb.get('data-block-type', '')
        if bt == 'html':
            text = xb.get_text(strip=True)
            if len(text) < 10:
                continue
            for tag in xb.find_all(['script', 'style', 'link']):
                tag.decompose()
            for div in xb.find_all('div', class_=re.compile(r'^h[1-6]$')):
                level = (div.get('class') or ['h2'])[0]
                new_tag = soup.new_tag(level)
                new_tag.string = div.get_text()
                div.replace_with(new_tag)
            content_div = xb.find('div', class_='main-block') or xb
            html_content = str(content_div)
            html_content = re.sub(r'src="//lms-cdn', 'src="https://lms-cdn', html_content)
            markdown = md(html_content, heading_style='atx', bullets='-', strip=['script', 'style', 'link'])
            markdown = re.sub(r'\n{3,}', '\n\n', markdown).strip()
            if markdown:
                results.append(markdown)
        elif bt == 'video':
            video_div = xb.find('div', attrs={'data-metadata': True})
            if video_div:
                try:
                    meta = json.loads(video_div.get('data-metadata', '{}'))
                    sources = meta.get('sources', [])
                    if sources:
                        results.append(f"\n> [!video] Видео\n> {sources[0]}\n")
                except (json.JSONDecodeError, TypeError):
                    pass
    return '\n\n---\n\n'.join(results)


def build_tree(blocks):
    course_block = None
    for bid, b in blocks.items():
        if b.get('type') == 'course':
            course_block = b
            break
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


def scrape_track(course_id, track_info):
    track_name = track_info['name']
    track_tag = track_info['tag']
    track_dir = VAULT / track_info['dir']
    track_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Scraping: {track_name} ({course_id})")
    print(f"{'='*60}")

    blocks = get_course_structure(course_id)
    tree = build_tree(blocks)
    print(f"Chapters: {len(tree)}")

    total = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0

    # Track MOC (replace placeholder)
    moc_lines = [
        '---',
        f'track: "{track_name}"',
        f'course_id: "{course_id}"',
        'tags:',
        f'  - {track_tag}',
        '  - type/track-hub',
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
        ch_name = sanitize_filename(chapter['name'])
        ch_dir = track_dir / f"{ch_idx:02d}. {ch_name}"
        ch_dir.mkdir(parents=True, exist_ok=True)

        moc_lines.append(f"## {chapter['name']}")
        moc_lines.append("")

        print(f"\n  Chapter {ch_idx}/{len(tree)}: {chapter['name']}")

        for sec_idx, section in enumerate(chapter['sections'], 1):
            sec_name = sanitize_filename(section['name'])
            print(f"    Section: {section['name']} ({len(section['units'])} units)")

            # Section aggregate
            sec_parts = [
                '---',
                f'section: "{section["name"]}"',
                f'chapter: "{chapter["name"]}"',
                f'track: "{track_name}"',
                'tags:',
                f'  - {track_tag}',
                '  - type/module',
                'aliases:',
                f'  - "{section["name"]}"',
                '---',
                '',
                f'> **nav:** [[{track_info["dir"]}/{track_name}|← {track_name}]]',
                '',
                f'# {section["name"]}',
                '',
            ]

            for unit_idx, unit in enumerate(section['units'], 1):
                processed += 1
                unit_name = sanitize_filename(unit['name'])
                print(f"      [{processed}/{total}] {unit['name']}...", end=' ', flush=True)

                try:
                    resp = session.get(f"{BASE_URL}/xblock/{unit['id']}", timeout=30)
                    resp.raise_for_status()
                    content = extract_content(resp.text)
                except Exception as e:
                    content = ""
                    print(f"ERROR: {e}")
                    continue

                time.sleep(DELAY)

                if content:
                    # Unit file
                    unit_file = ch_dir / f"{sec_idx:02d}-{unit_idx:02d}. {unit_name}.md"
                    unit_fm = (
                        f"---\n"
                        f"unit: \"{unit['name']}\"\n"
                        f"section: \"{section['name']}\"\n"
                        f"chapter: \"{chapter['name']}\"\n"
                        f"track: \"{track_name}\"\n"
                        f"tags:\n"
                        f"  - {track_tag}\n"
                        f"  - type/lesson\n"
                        f"---\n\n"
                        f"# {unit['name']}\n\n"
                        f"> **nav:** [[{track_info['dir']}/{ch_idx:02d}. {ch_name}/{sec_name}|← {section['name']}]]\n\n"
                    )
                    unit_file.write_text(unit_fm + content, encoding='utf-8')
                    sec_parts.append(f"## {unit['name']}")
                    sec_parts.append("")
                    sec_parts.append(content)
                    sec_parts.append("")
                    print(f"OK ({len(content)} chars)")
                else:
                    print("EMPTY")

            # Write section file
            sec_file = ch_dir / f"{sec_name}.md"
            sec_file.write_text('\n'.join(sec_parts), encoding='utf-8')
            moc_lines.append(f"- [[{track_info['dir']}/{ch_idx:02d}. {ch_name}/{sec_name}|{section['name']}]]")

        moc_lines.append("")

    # Write track MOC
    moc_file = VAULT / f"{track_name}.md"
    moc_file.write_text('\n'.join(moc_lines), encoding='utf-8')
    print(f"\nDone: {track_name} — {processed} units")


def main():
    for course_id, track_info in TRACKS.items():
        scrape_track(course_id, track_info)
    print("\nAll tracks scraped!")


if __name__ == '__main__':
    main()
