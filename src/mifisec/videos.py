"""Stage 3: Download lecture recordings from Kinescope."""

import re
import subprocess
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

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
        'ffmpeg', '-y',
        '-headers', 'Referer: https://lms.skillfactory.ru/\r\n',
        '-i', m3u8_url,
        '-map', '0:v:0', '-map', '0:a:0',
        '-c', 'copy', '-movflags', '+faststart',
        str(output),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=3600)
        return result.returncode == 0 and output.exists() and output.stat().st_size > 1024
    except (subprocess.TimeoutExpired, OSError):
        return False


def download_videos(session: requests.Session, output_dir: Path,
                    quality: int = 720, limit: int = 0, list_only: bool = False):
    """Main entry: find recordings, download via ffmpeg."""
    from .scraper import get_course_structure

    videos_dir = output_dir / "_videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    all_recordings = []
    for course_id, course_label in [
        (COURSES['main']['id'], 'main'),
        (COURSES['pentest']['id'], 'pentest'),
    ]:
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
    success = failed = skipped = 0

    for i, rec in enumerate(all_recordings[:max_items], 1):
        chapter_safe = sanitize(rec['chapter'], 60) or 'other'
        name_safe = sanitize(rec['name'], 60)
        output_file = videos_dir / chapter_safe / f"{name_safe}.mp4"

        if output_file.exists() and output_file.stat().st_size > 1024:
            skipped += 1
            continue

        print(f"  [{i}/{max_items}] {rec['chapter']} / {rec['name']}...", end=' ', flush=True)

        kinescope_url = get_kinescope_url(session, rec['id'])
        time.sleep(0.5)
        if not kinescope_url:
            print("NO VIDEO"); failed += 1; continue

        m3u8_url = get_hls_manifest(kinescope_url)
        if not m3u8_url:
            print("NO MANIFEST"); failed += 1; continue

        print(f"downloading...", end=' ', flush=True)
        if download_with_ffmpeg(m3u8_url, output_file):
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"OK ({size_mb:.0f} MB)")
            success += 1
        else:
            print("FAILED"); failed += 1

    print(f"\nDone: {success} downloaded, {skipped} cached, {failed} failed")
    total_size = sum(f.stat().st_size for f in videos_dir.rglob('*.mp4'))
    print(f"Total video size: {total_size / 1024 / 1024 / 1024:.1f} GB")
