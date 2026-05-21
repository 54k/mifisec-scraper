"""Stage 3: Download lecture recordings from Kinescope."""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

VIDEO_WORKERS = 4

from .utils import BASE_URL, COURSES, sanitize


def find_recording_verticals(blocks: dict) -> list[dict]:
    """Find all verticals inside 'Записи' sequentials."""
    results = []
    for bid, b in blocks.items():
        if b.get('type') != 'sequential':
            continue
        name = b.get('display_name', '')
        if 'Записи' not in name and 'записи' not in name:
            continue
        chapter_name = ""
        for pbid, pb in blocks.items():
            if pb.get('type') == 'chapter' and bid in pb.get('children', []):
                chapter_name = pb.get('display_name', '')
                break
        for child_id in b.get('children', []):
            child = blocks.get(child_id, {})
            if child.get('type') == 'vertical':
                results.append({
                    'id': child_id,
                    'name': child.get('display_name', '?'),
                    'section': name,
                    'chapter': chapter_name,
                })
    return results


def get_kinescope_url(session: requests.Session, vertical_id: str) -> str | None:
    """Fetch vertical page and extract kinescope embed URL."""
    try:
        resp = session.get(f"{BASE_URL}/xblock/{vertical_id}", timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    soup = BeautifulSoup(resp.text, 'html.parser')
    for iframe in soup.find_all('iframe'):
        src = iframe.get('src', '')
        if 'kinescope.io/embed/' in src:
            return src
    return None


def get_hls_manifest(kinescope_url: str) -> str | None:
    """Get HLS m3u8 URL from kinescope embed page."""
    try:
        resp = requests.get(kinescope_url, headers={
            'Referer': 'https://lms.skillfactory.ru/',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        }, timeout=15)
        if resp.status_code != 200:
            return None
    except requests.RequestException:
        return None
    match = re.search(r'(https://kinescope\.io/[a-f0-9\-]+/master\.m3u8\?[^"\\]+)', resp.text)
    if match:
        return match.group(1).replace('\\u0026', '&').replace('&amp;', '&')
    return None


def download_with_ffmpeg(m3u8_url: str, output: Path) -> bool:
    """Download HLS stream using ffmpeg."""
    if output.exists() and output.stat().st_size > 1024:
        return True
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-headers', 'Referer: https://lms.skillfactory.ru/\r\n',
        '-i', m3u8_url,
        '-map', '0:v:0', '-map', '0:a:0',
        '-c', 'copy',
        str(output),
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=7200,
        )
        return result.returncode == 0 and output.exists() and output.stat().st_size > 1024
    except (subprocess.TimeoutExpired, OSError):
        if output.exists():
            output.unlink()
        return False


def _download_one_video(session: requests.Session, rec: dict, videos_dir: Path) -> tuple[str, str]:
    """Download a single video. Returns (name, status)."""
    chapter_safe = sanitize(rec['chapter'], 60) or 'other'
    name_safe = sanitize(rec['name'], 60)
    output_file = videos_dir / chapter_safe / f"{name_safe}.mp4"

    if output_file.exists() and output_file.stat().st_size > 1024:
        return (rec['name'], "cached")

    kinescope_url = get_kinescope_url(session, rec['id'])
    if not kinescope_url:
        return (rec['name'], "no_video")

    m3u8_url = get_hls_manifest(kinescope_url)
    if not m3u8_url:
        return (rec['name'], "no_manifest")

    ok = download_with_ffmpeg(m3u8_url, output_file)

    # Retry with fresh manifest if failed
    if not ok:
        m3u8_url = get_hls_manifest(kinescope_url)
        if m3u8_url:
            ok = download_with_ffmpeg(m3u8_url, output_file)

    if ok:
        size_mb = output_file.stat().st_size / 1024 / 1024
        return (rec['name'], f"ok:{size_mb:.0f}MB")
    return (rec['name'], "failed")


def download_videos(session: requests.Session, output_dir: Path,
                    quality: int = 720, limit: int = 0, list_only: bool = False):
    """Main entry: find recordings, download via ffmpeg (4 parallel)."""
    from .scraper import get_course_structure, get_enrollments

    videos_dir = output_dir / "_videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # Scan only courses that exist in vault
    all_recordings = []
    courses_to_scan = []

    # Check which courses are actually in the vault
    if (output_dir / 'Семестр 1').exists():
        courses_to_scan.append((COURSES['main']['id'], 'main'))
    if (output_dir / COURSES['pentest']['name']).exists():
        courses_to_scan.append((COURSES['pentest']['id'], 'pentest'))
    if (output_dir / COURSES['compliance']['name']).exists():
        courses_to_scan.append((COURSES['compliance']['id'], 'compliance'))

    # Also check for any other course dirs
    known_dirs = {'Семестр 1', 'Семестр 2', 'Семестр 3', 'Семестр 4',
                  'ДПО и факультативы', COURSES['pentest']['name'],
                  COURSES['compliance']['name'], '_assets', '_videos', '.obsidian'}
    for d in output_dir.iterdir():
        if d.is_dir() and d.name not in known_dirs and not d.name.startswith(('.', '_')):
            # Unknown course dir — try to find its course_id
            try:
                enrollments = get_enrollments(session)
                for e in enrollments:
                    if e['name'] == d.name or sanitize(e['name']) == d.name:
                        courses_to_scan.append((e['id'], e['name']))
                        break
            except Exception:
                pass

    if not courses_to_scan:
        print("  Нет скачанных курсов для поиска видео")
        return

    for course_id, course_label in courses_to_scan:
        print(f"Scanning: {course_label}...")
        try:
            blocks = get_course_structure(session, course_id)
            recs = find_recording_verticals(blocks)
            for r in recs:
                r['course'] = course_label
            all_recordings.extend(recs)
            print(f"  Found {len(recs)} recordings")
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nTotal recordings: {len(all_recordings)}")

    if list_only:
        for r in all_recordings:
            print(f"  [{r['course']}] {r['chapter']} / {r['name']}")
        return

    max_items = limit or len(all_recordings)
    to_download = all_recordings[:max_items]

    # Filter out already cached
    pending = []
    skipped = 0
    for rec in to_download:
        chapter_safe = sanitize(rec['chapter'], 60) or 'other'
        name_safe = sanitize(rec['name'], 60)
        output_file = videos_dir / chapter_safe / f"{name_safe}.mp4"
        if output_file.exists() and output_file.stat().st_size > 1024:
            skipped += 1
        else:
            pending.append(rec)

    if skipped:
        print(f"  Cached: {skipped}, to download: {len(pending)}")

    if not pending:
        print("  All videos already downloaded")
    else:
        success = failed = 0
        with ThreadPoolExecutor(max_workers=VIDEO_WORKERS) as executor:
            futures = {executor.submit(_download_one_video, session, rec, videos_dir): rec
                       for rec in pending}
            done = 0
            for future in as_completed(futures):
                done += 1
                name, status = future.result()
                if status.startswith("ok:"):
                    success += 1
                    print(f"  [{done}/{len(pending)}] {name}... {status}")
                elif status == "cached":
                    skipped += 1
                else:
                    failed += 1
                    print(f"  [{done}/{len(pending)}] {name}... {status.upper()}")

        print(f"\nDone: {success} downloaded, {skipped} cached, {failed} failed")

    total_size = sum(f.stat().st_size for f in videos_dir.rglob('*.mp4'))
    print(f"Total video size: {total_size / 1024 / 1024 / 1024:.1f} GB")

    # Link videos to their markdown files
    print(f"\nLinking videos to vault notes...")
    linked = link_videos_to_vault(output_dir, videos_dir)
    print(f"  Linked {linked} videos to notes")


def link_videos_to_vault(vault_dir: Path, videos_dir: Path) -> int:
    """Find corresponding markdown files and insert ![[video.mp4]] embeds."""
    linked = 0

    # Build index: strip numeric prefix from md filenames for matching
    # "01. Занятие 1. 05.09.md" → "Занятие 1. 05.09"
    md_index = {}  # clean_stem → md_file path
    for md_file in vault_dir.rglob('*.md'):
        if md_file.is_relative_to(videos_dir):
            continue
        if md_file.is_relative_to(vault_dir / '_assets'):
            continue
        # Strip leading "NN. " prefix
        clean = re.sub(r'^\d+[\.\-]\s*', '', md_file.stem)
        md_index.setdefault(clean.lower(), []).append(md_file)

    for mp4 in videos_dir.rglob('*.mp4'):
        video_name = mp4.name
        embed = f'![[{video_name}]]'
        stem = mp4.stem  # "Занятие 1. 05.09" or "26.02.2025 Встреча..."

        # Find matching md file
        candidates = md_index.get(stem.lower(), [])

        # If no exact match, try substring search in "Записи" sections
        if not candidates:
            for md_file in vault_dir.rglob('*.md'):
                if md_file.is_relative_to(videos_dir) or md_file.is_relative_to(vault_dir / '_assets'):
                    continue
                if 'Записи' in str(md_file) or 'записи' in str(md_file):
                    clean_md = re.sub(r'^\d+[\.\-]\s*', '', md_file.stem)
                    if stem.lower() == clean_md.lower():
                        candidates.append(md_file)

        if not candidates:
            # No matching .md exists — find the section aggregate and append there
            # Look for section "Записи" files in matching chapter
            chapter_dir_name = mp4.parent.name  # e.g. "IV. Выпускная квалификационная работа"
            for md_file in vault_dir.rglob('*.md'):
                if md_file.is_relative_to(videos_dir):
                    continue
                if chapter_dir_name.lower() in str(md_file).lower() and 'записи' in str(md_file).lower():
                    if md_file.stem.lower().startswith('записи'):
                        candidates.append(md_file)
                        break

        for md_file in candidates:
            content = md_file.read_text(encoding='utf-8')
            if embed in content:
                linked += 1  # already linked, count as success
                break
            # Insert after heading
            lines = content.split('\n')
            inserted = False
            for i, line in enumerate(lines):
                if line.startswith('# '):
                    lines.insert(i + 1, f'\n{embed}\n')
                    inserted = True
                    break
            if not inserted:
                lines.append(f'\n{embed}\n')
            md_file.write_text('\n'.join(lines), encoding='utf-8')
            linked += 1
            break

    return linked
