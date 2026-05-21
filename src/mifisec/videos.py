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



def download_videos(session: requests.Session, output_dir: Path,
                    quality: int = 720, limit: int = 0, list_only: bool = False):
    """Main entry: find recordings, download via ffmpeg (4 parallel)."""
    from .scraper import get_course_structure, get_enrollments

    videos_dir = output_dir / "_videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    # Scan all enrolled courses for recordings
    all_recordings = []

    print("  Поиск записей во всех курсах...")
    try:
        enrollments = get_enrollments(session)
    except Exception as e:
        print(f"  Ошибка получения списка курсов: {e}")
        return

    for course in enrollments:
        try:
            blocks = get_course_structure(session, course['id'])
            recs = find_recording_verticals(blocks)
            if recs:
                for r in recs:
                    r['course'] = course['name']
                all_recordings.extend(recs)
                print(f"    {course['name']}: {len(recs)} записей")
        except Exception:
            pass

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
        total_pending = len(pending)

        # Process in batches of VIDEO_WORKERS
        for batch_start in range(0, total_pending, VIDEO_WORKERS):
            batch = pending[batch_start:batch_start + VIDEO_WORKERS]

            # Resolve manifests sequentially (fast, needs session)
            jobs = []  # (rec, m3u8_url, output_file)
            for rec in batch:
                chapter_safe = sanitize(rec['chapter'], 60) or 'other'
                name_safe = sanitize(rec['name'], 60)
                output_file = videos_dir / chapter_safe / f"{name_safe}.mp4"
                idx = batch_start + len(jobs) + 1

                print(f"  [{idx}/{total_pending}] {rec['name']}...", end=' ', flush=True)
                kinescope_url = get_kinescope_url(session, rec['id'])
                if not kinescope_url:
                    print("NO VIDEO")
                    failed += 1
                    continue
                m3u8_url = get_hls_manifest(kinescope_url)
                if not m3u8_url:
                    print("NO MANIFEST")
                    failed += 1
                    continue
                print("downloading...", flush=True)
                jobs.append((rec, m3u8_url, output_file))

            # Download batch in parallel (ffmpeg subprocesses)
            if jobs:
                with ThreadPoolExecutor(max_workers=VIDEO_WORKERS) as executor:
                    futures = {executor.submit(download_with_ffmpeg, m3u8, out): (rec, out)
                               for rec, m3u8, out in jobs}
                    for future in as_completed(futures):
                        rec, out = futures[future]
                        ok = future.result()
                        if ok:
                            size_mb = out.stat().st_size / 1024 / 1024
                            print(f"    -> {rec['name']}: OK ({size_mb:.0f} MB)", flush=True)
                            success += 1
                        else:
                            print(f"    -> {rec['name']}: FAILED", flush=True)
                            failed += 1

        print(f"\nDone: {success} downloaded, {skipped} cached, {failed} failed")

    total_size = sum(f.stat().st_size for f in videos_dir.rglob('*.mp4'))
    print(f"Total video size: {total_size / 1024 / 1024 / 1024:.1f} GB")

    # Link videos to their markdown files
    print(f"\nLinking videos to vault notes...")
    linked = link_videos_to_vault(output_dir, videos_dir)
    print(f"  Linked {linked} videos to notes")


def _parse_date_from_name(name: str) -> tuple:
    """Extract date from video filename for sorting. Returns sortable tuple."""
    import re as _re
    # Try DD.MM.YYYY or DD.MM.YY
    m = _re.search(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})', name)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        return (year, month, day, name)
    # Try "Занятие N. DD.MM" pattern
    m = _re.search(r'(\d{1,2})\.(\d{1,2})$', name)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        return (2024, month, day, name)  # assume 2024 if no year
    # Try "#N" pattern (Занятие 1, Занятие 2...)
    m = _re.search(r'(\d+)', name)
    if m:
        return (0, 0, int(m.group(1)), name)
    return (9999, 0, 0, name)


def link_videos_to_vault(vault_dir: Path, videos_dir: Path) -> int:
    """Find corresponding markdown files and insert ![[video.mp4]] embeds in chronological order."""
    # Build index: strip numeric prefix from md filenames
    md_index = {}  # clean_stem → [md_file paths]
    for md_file in vault_dir.rglob('*.md'):
        if md_file.is_relative_to(videos_dir) or md_file.is_relative_to(vault_dir / '_assets'):
            continue
        clean = re.sub(r'^\d+[\.\-]\s*', '', md_file.stem)
        md_index.setdefault(clean.lower(), []).append(md_file)

    # Phase 1: map each video to its target md file
    # target_file → [mp4_names]
    file_videos = {}  # md_file → list of video filenames

    for mp4 in videos_dir.rglob('*.mp4'):
        stem = mp4.stem
        target = None

        # Try exact match by name
        candidates = md_index.get(stem.lower(), [])

        # Try "Записи" sections
        if not candidates:
            for md_file in vault_dir.rglob('*.md'):
                if md_file.is_relative_to(videos_dir) or md_file.is_relative_to(vault_dir / '_assets'):
                    continue
                if 'Записи' in str(md_file) or 'записи' in str(md_file):
                    clean_md = re.sub(r'^\d+[\.\-]\s*', '', md_file.stem)
                    if stem.lower() == clean_md.lower():
                        candidates.append(md_file)

        # Fallback: section aggregate in matching chapter
        if not candidates:
            chapter_dir_name = mp4.parent.name
            for md_file in vault_dir.rglob('*.md'):
                if md_file.is_relative_to(videos_dir):
                    continue
                if chapter_dir_name.lower() in str(md_file).lower() and 'записи' in str(md_file).lower():
                    if md_file.stem.lower().startswith('записи'):
                        candidates.append(md_file)
                        break

        if candidates:
            target = candidates[0]
            file_videos.setdefault(target, []).append(mp4.name)

    # Phase 2: for each target file, sort videos chronologically and write
    linked = 0
    for md_file, video_names in file_videos.items():
        content = md_file.read_text(encoding='utf-8')

        # Remove existing video embeds (we'll rewrite them sorted)
        lines = content.split('\n')
        lines = [l for l in lines if not (l.strip().startswith('![[') and l.strip().endswith('.mp4]]'))]
        content = '\n'.join(lines)

        # Sort videos by date
        video_names.sort(key=lambda n: _parse_date_from_name(n.replace('.mp4', '')))

        # Filter out already present
        to_insert = [f'![[{name}]]' for name in video_names]

        # Insert after first heading
        lines = content.split('\n')
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith('# '):
                insert_idx = i + 1
                break

        # Add sorted video block
        video_block = '\n' + '\n\n'.join(to_insert) + '\n'
        lines.insert(insert_idx, video_block)

        md_file.write_text('\n'.join(lines), encoding='utf-8')
        linked += len(video_names)

    return linked
