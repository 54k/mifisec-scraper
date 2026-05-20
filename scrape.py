#!/usr/bin/env python3
"""
SkillFactory Open edX Course Scraper → Obsidian Markdown

Скачивает курс "Безопасность информационных систем" (MIFISEC)
и конвертирует в структурированный Obsidian vault.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# === CONFIG ===
COURSE_ID = "course-v1:SkillFactory+MIFISEC+SEP_2023"
BASE_URL = "https://lms.skillfactory.ru"
OUTPUT_DIR = Path(__file__).parent / "vault"
ASSETS_DIR = OUTPUT_DIR / "_assets"
DELAY = 0.5  # seconds between requests
COOKIES_FILE = Path(__file__).parent / "cookies.json"


def load_cookies() -> dict:
    """Load cookies from cookies.json file."""
    if not COOKIES_FILE.exists():
        print(f"ERROR: {COOKIES_FILE} not found!")
        print()
        print("Инструкция:")
        print("1. Залогинься на https://student-lk.skillfactory.ru/my-study")
        print("2. Открой DevTools (F12) → Application → Cookies → skillfactory.ru")
        print("3. Скопируй значения 3 cookies в файл cookies.json:")
        print()
        print('  {')
        print('    "sessionid": "...",')
        print('    "edx-jwt-cookie-header-payload": "...",')
        print('    "edx-jwt-cookie-signature": "..."')
        print('  }')
        print()
        print("Или экспортируй cookies через расширение браузера (Cookie-Editor и т.д.)")
        raise SystemExit(1)

    with open(COOKIES_FILE, 'r') as f:
        data = json.load(f)

    # Support both flat format and Cookie-Editor array export
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def sanitize_filename(name: str) -> str:
    """Clean up a string for use as filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = name[:100]  # limit length
    return name


def get_course_structure():
    """Fetch full course outline from API."""
    url = f"{BASE_URL}/api/course_home/outline/{COURSE_ID}"
    resp = session.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data['course_blocks']['blocks']


def extract_content_from_html(html: str) -> list[dict]:
    """Parse xblock page and extract content blocks."""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Find all xblock divs with data-block-type
    xblocks = soup.find_all('div', class_='xblock', attrs={'data-block-type': True})

    for xblock in xblocks:
        block_type = xblock.get('data-block-type', '')

        if block_type == 'html':
            # Skip blocks that have no text content (CSS/font wrappers)
            text_content = xblock.get_text(strip=True)
            if len(text_content) < 10:
                continue

            # Remove scripts, styles, links
            for tag in xblock.find_all(['script', 'style', 'link']):
                tag.decompose()

            # Convert SF custom heading classes to real headings
            for div in xblock.find_all('div', class_=re.compile(r'^h[1-6]$')):
                level = div.get('class', ['h2'])[0]  # e.g. 'h2'
                new_tag = soup.new_tag(level)
                new_tag.string = div.get_text()
                div.replace_with(new_tag)

            # Get content from main-block or the whole xblock
            content_div = xblock.find('div', class_='main-block')
            if not content_div:
                content_div = xblock

            html_content = str(content_div)
            if len(html_content.strip()) < 50:
                continue

            results.append({
                'type': 'html',
                'content': html_content,
            })

        elif block_type == 'video':
            # Extract video metadata
            video_data = {}
            init_args = xblock.find('script', class_='xblock-json-init-args')
            if init_args:
                try:
                    args = json.loads(init_args.string)
                    video_data = args
                except (json.JSONDecodeError, TypeError):
                    pass

            # Try to find video sources
            video_tag = xblock.find('video')
            sources = []
            if video_tag:
                for source in video_tag.find_all('source'):
                    sources.append(source.get('src', ''))

            # Look for data attributes with video URL
            video_wrapper = xblock.find('div', class_='video')
            metadata = {}
            if video_wrapper:
                data_metadata = video_wrapper.get('data-metadata', '')
                if data_metadata:
                    try:
                        metadata = json.loads(data_metadata)
                    except json.JSONDecodeError:
                        pass

            # Extract from xblock initialization data
            video_init = xblock.find('div', attrs={'data-video-id': True})
            video_id = ''
            if video_init:
                video_id = video_init.get('data-video-id', '')

            results.append({
                'type': 'video',
                'sources': sources,
                'metadata': metadata,
                'video_id': video_id,
                'raw_data': video_data,
            })

        elif block_type == 'problem':
            # Extract problem/quiz content
            problem_div = xblock.find('div', class_='problems-wrapper')
            if not problem_div:
                problem_div = xblock
            scripts = problem_div.find_all('script')
            for s in scripts:
                s.decompose()
            results.append({
                'type': 'problem',
                'content': str(problem_div),
            })

    return results


def html_to_markdown(html_content: str) -> str:
    """Convert HTML to clean Obsidian-compatible markdown."""
    # Pre-process: fix relative URLs
    html_content = re.sub(
        r'src="//lms-cdn\.skillfactory\.ru',
        'src="https://lms-cdn.skillfactory.ru',
        html_content
    )
    html_content = re.sub(
        r'href="//lms-cdn\.skillfactory\.ru',
        'href="https://lms-cdn.skillfactory.ru',
        html_content
    )

    # Convert
    markdown = md(
        html_content,
        heading_style="atx",
        bullets="-",
        code_language="",
        strip=['script', 'style', 'link'],
    )

    # Clean up
    markdown = re.sub(r'\n{3,}', '\n\n', markdown)
    markdown = re.sub(r'[ \t]+\n', '\n', markdown)
    markdown = markdown.strip()

    return markdown


def format_video_block(video: dict) -> str:
    """Format video block as markdown."""
    lines = ["\n> [!video] Видео"]
    sources = video.get('sources', [])
    if sources:
        for src in sources:
            lines.append(f"> {src}")
    video_id = video.get('video_id', '')
    if video_id:
        lines.append(f"> Video ID: `{video_id}`")
    metadata = video.get('metadata', {})
    if metadata:
        if 'youtube_id' in metadata or 'youTubeId' in metadata:
            yt_id = metadata.get('youtube_id', metadata.get('youTubeId', ''))
            if yt_id:
                lines.append(f"> YouTube: https://youtube.com/watch?v={yt_id}")
    lines.append("")
    return '\n'.join(lines)


def format_problem_block(problem: dict) -> str:
    """Format problem/quiz block as markdown."""
    content = html_to_markdown(problem['content'])
    if not content.strip():
        return ""
    return f"\n> [!question] Задание\n> {content.replace(chr(10), chr(10) + '> ')}\n"


def process_vertical(block_id: str) -> str:
    """Fetch and process a single vertical (lesson page)."""
    url = f"{BASE_URL}/xblock/{block_id}"
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"*Ошибка загрузки: {e}*"

    blocks = extract_content_from_html(resp.text)
    parts = []

    for block in blocks:
        if block['type'] == 'html':
            md_content = html_to_markdown(block['content'])
            if md_content:
                parts.append(md_content)
        elif block['type'] == 'video':
            parts.append(format_video_block(block))
        elif block['type'] == 'problem':
            parts.append(format_problem_block(block))

    return '\n\n---\n\n'.join(parts) if parts else ""


def build_tree(blocks: dict) -> list[dict]:
    """Build ordered course tree from flat blocks dict."""
    # Find course root
    course_block = None
    for bid, b in blocks.items():
        if b.get('type') == 'course':
            course_block = b
            course_block['_id'] = bid
            break

    if not course_block:
        raise ValueError("Course block not found")

    tree = []
    for ch_id in course_block.get('children', []):
        ch = blocks.get(ch_id, {})
        chapter = {
            'id': ch_id,
            'name': ch.get('display_name', 'Unknown'),
            'type': 'chapter',
            'sections': [],
        }
        for seq_id in ch.get('children', []):
            seq = blocks.get(seq_id, {})
            section = {
                'id': seq_id,
                'name': seq.get('display_name', 'Unknown'),
                'type': 'sequential',
                'units': [],
            }
            for vert_id in seq.get('children', []):
                vert = blocks.get(vert_id, {})
                unit = {
                    'id': vert_id,
                    'name': vert.get('display_name', 'Unknown'),
                    'type': 'vertical',
                }
                section['units'].append(unit)
            chapter['sections'].append(section)
        tree.append(chapter)

    return tree


def semester_prefix(name: str) -> str:
    """Extract semester number for sorting."""
    m = re.match(r'^(I{1,4}V?|ДПО)', name)
    if m:
        roman = m.group(1)
        mapping = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'ДПО': '5'}
        return mapping.get(roman, '9')
    return '9'


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("Fetching course structure...")
    blocks = get_course_structure()
    tree = build_tree(blocks)

    # Save structure for reference
    with open(OUTPUT_DIR / "_structure.json", 'w', encoding='utf-8') as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    print(f"Course has {len(tree)} chapters")

    # Sort chapters by semester
    tree.sort(key=lambda ch: semester_prefix(ch['name']))

    total_units = sum(len(s['units']) for ch in tree for s in ch['sections'])
    processed = 0
    errors = 0

    for ch_idx, chapter in enumerate(tree, 1):
        ch_name = sanitize_filename(chapter['name'])
        ch_dir = OUTPUT_DIR / f"{ch_idx:02d}. {ch_name}"
        ch_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"Chapter {ch_idx}/{len(tree)}: {chapter['name']}")
        print(f"{'='*60}")

        # Chapter MOC
        moc_lines = [
            f"---",
            f"chapter: \"{chapter['name']}\"",
            f"course: MIFISEC",
            f"---",
            f"",
            f"# {chapter['name']}",
            f"",
        ]

        for sec_idx, section in enumerate(chapter['sections'], 1):
            sec_name = sanitize_filename(section['name'])
            sec_dir = ch_dir / f"{sec_idx:02d}. {sec_name}"
            sec_dir.mkdir(parents=True, exist_ok=True)

            moc_lines.append(f"## {section['name']}")
            moc_lines.append("")

            print(f"  Section {sec_idx}: {section['name']} ({len(section['units'])} units)")

            # Section file - combines all units in sequence
            section_parts = [
                f"---",
                f"section: \"{section['name']}\"",
                f"chapter: \"{chapter['name']}\"",
                f"course: MIFISEC",
                f"---",
                f"",
                f"# {section['name']}",
                f"",
            ]

            for unit_idx, unit in enumerate(section['units'], 1):
                unit_name = sanitize_filename(unit['name'])
                processed += 1

                print(f"    [{processed}/{total_units}] {unit['name']}...", end=' ', flush=True)

                content = process_vertical(unit['id'])
                time.sleep(DELAY)

                if content:
                    # Individual unit file
                    unit_file = sec_dir / f"{unit_idx:02d}. {unit_name}.md"
                    unit_frontmatter = (
                        f"---\n"
                        f"unit: \"{unit['name']}\"\n"
                        f"section: \"{section['name']}\"\n"
                        f"chapter: \"{chapter['name']}\"\n"
                        f"course: MIFISEC\n"
                        f"---\n\n"
                        f"# {unit['name']}\n\n"
                    )
                    unit_file.write_text(unit_frontmatter + content, encoding='utf-8')

                    # Add to section aggregate
                    section_parts.append(f"## {unit['name']}")
                    section_parts.append("")
                    section_parts.append(content)
                    section_parts.append("")

                    # Add to MOC
                    rel_path = f"{sec_idx:02d}. {sec_name}/{unit_idx:02d}. {unit_name}"
                    moc_lines.append(f"- [[{rel_path}|{unit['name']}]]")

                    print(f"OK ({len(content)} chars)")
                else:
                    print("EMPTY")
                    errors += 1

            moc_lines.append("")

            # Write section aggregate file
            section_file = sec_dir / f"_section.md"
            section_file.write_text('\n'.join(section_parts), encoding='utf-8')

        # Write chapter MOC
        moc_file = ch_dir / f"_MOC.md"
        moc_file.write_text('\n'.join(moc_lines), encoding='utf-8')

    # Write root MOC
    root_moc = [
        "---",
        "course: MIFISEC",
        "university: НИЯУ МИФИ",
        "program: Безопасность информационных систем",
        "---",
        "",
        "# Безопасность информационных систем",
        "",
        "Магистратура НИЯУ МИФИ × SkillFactory",
        "",
    ]
    for ch_idx, chapter in enumerate(tree, 1):
        ch_name = sanitize_filename(chapter['name'])
        root_moc.append(f"## {chapter['name']}")
        root_moc.append("")
        for sec_idx, section in enumerate(chapter['sections'], 1):
            sec_name = sanitize_filename(section['name'])
            root_moc.append(f"- [[{ch_idx:02d}. {ch_name}/{sec_idx:02d}. {sec_name}/_section|{section['name']}]]")
        root_moc.append("")

    (OUTPUT_DIR / "index.md").write_text('\n'.join(root_moc), encoding='utf-8')

    print(f"\n{'='*60}")
    print(f"DONE: {processed} units processed, {errors} empty/errors")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
