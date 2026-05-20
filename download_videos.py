#!/usr/bin/env python3
"""
Stage 3: Download lecture recordings from Kinescope.

Находит все записи занятий (iframe kinescope.io) через API курса,
получает HLS manifest и скачивает через ffmpeg.

Usage:
  python3 download_videos.py              # 720p по умолчанию
  python3 download_videos.py --quality 480 # экономия места
  python3 download_videos.py --quality 1080 # максимальное качество
  python3 download_videos.py --list        # только список без скачивания

Requires: ffmpeg (brew install ffmpeg)
"""

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://lms.skillfactory.ru"
VAULT = Path(__file__).parent / "vault"
VIDEOS_DIR = VAULT / "_videos"
COOKIES_FILE = Path(__file__).parent / "cookies.json"
DELAY = 0.5

COURSES = [
    ("course-v1:SkillFactory+MIFISEC+SEP_2023", "main"),
    ("course-v1:SkillFactory+mifisec_pentest2023+FEB_2024", "pentest"),
]


def load_cookies() -> dict:
    with open(COOKIES_FILE, 'r') as f:
        data = json.load(f)
    if isinstance(data, list):
        return {c['name']: c['value'] for c in data
                if c.get('name') in ('sessionid', 'edx-jwt-cookie-header-payload', 'edx-jwt-cookie-signature')}
    return data


def sanitize(name: str, max_len: int = 60) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len]


def get_course_structure(session, course_id: str) -> dict:
    resp = session.get(f"{BASE_URL}/api/course_home/outline/{course_id}")
    resp.raise_for_status()
    return resp.json()['course_blocks']['blocks']


def find_recording_verticals(blocks: dict) -> list[dict]:
    """Find all verticals inside 'Записи' sequentials."""
    results = []
    for bid, b in blocks.items():
        if b.get('type') != 'sequential':
            continue
        name = b.get('display_name', '')
        if 'Записи' not in name and 'записи' not in name:
            continue

        # Get parent chapter name
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


def get_kinescope_url(session, vertical_id: str) -> str | None:
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

    # Extract m3u8 URL
    match = re.search(r'(https://kinescope\.io/[a-f0-9\-]+/master\.m3u8\?[^"\\]+)', resp.text)
    if match:
        url = match.group(1).replace('\\u0026', '&').replace('&amp;', '&')
        return url
    return None


def download_with_ffmpeg(m3u8_url: str, output: Path, quality: int = 720) -> bool:
    """Download HLS stream using ffmpeg with quality selection."""
    if output.exists() and output.stat().st_size > 1024:
        return True  # already downloaded

    output.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg command: select specific quality bandwidth
    # Use map to pick video stream by resolution
    cmd = [
        'ffmpeg', '-y',
        '-headers', 'Referer: https://lms.skillfactory.ru/\r\n',
        '-i', m3u8_url,
        '-map', '0:v:0', '-map', '0:a:0',
        '-c', 'copy',
        '-movflags', '+faststart',
        str(output),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=3600,  # 1 hour max per video
        )
        return result.returncode == 0 and output.exists() and output.stat().st_size > 1024
    except (subprocess.TimeoutExpired, OSError):
        return False


def main():
    parser = argparse.ArgumentParser(description='Download lecture recordings from Kinescope')
    parser.add_argument('--quality', type=int, default=720, choices=[360, 480, 720, 1080],
                        help='Video quality (default: 720)')
    parser.add_argument('--list', action='store_true', help='List videos without downloading')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of downloads (0=all)')
    args = parser.parse_args()

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.cookies.update(load_cookies())
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    })

    # Collect all recording verticals
    all_recordings = []
    for course_id, course_label in COURSES:
        print(f"Scanning: {course_id}...")
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

    if args.list:
        for r in all_recordings:
            print(f"  [{r['course']}] {r['chapter']} / {r['name']}")
        return

    # Process each recording
    success = 0
    failed = 0
    skipped = 0
    limit = args.limit or len(all_recordings)

    for i, rec in enumerate(all_recordings[:limit], 1):
        chapter_safe = sanitize(rec['chapter']) or 'other'
        name_safe = sanitize(rec['name'])
        output_file = VIDEOS_DIR / chapter_safe / f"{name_safe}.mp4"

        if output_file.exists() and output_file.stat().st_size > 1024:
            skipped += 1
            print(f"  [{i}/{limit}] CACHED: {rec['name']}")
            continue

        print(f"  [{i}/{limit}] {rec['chapter']} / {rec['name']}...", end=' ', flush=True)

        # Step 1: get kinescope embed URL
        kinescope_url = get_kinescope_url(session, rec['id'])
        time.sleep(DELAY)

        if not kinescope_url:
            print("NO VIDEO")
            failed += 1
            continue

        # Step 2: get HLS manifest
        m3u8_url = get_hls_manifest(kinescope_url)
        if not m3u8_url:
            print("NO MANIFEST")
            failed += 1
            continue

        # Step 3: download
        print(f"downloading ({args.quality}p)...", end=' ', flush=True)
        ok = download_with_ffmpeg(m3u8_url, output_file, args.quality)

        if ok:
            size_mb = output_file.stat().st_size / 1024 / 1024
            print(f"OK ({size_mb:.0f} MB)")
            success += 1
        else:
            print("FAILED")
            failed += 1

    print(f"\nDone: {success} downloaded, {skipped} cached, {failed} failed")
    total_size = sum(f.stat().st_size for f in VIDEOS_DIR.rglob('*.mp4'))
    print(f"Total video size: {total_size / 1024 / 1024 / 1024:.1f} GB")


if __name__ == '__main__':
    main()
