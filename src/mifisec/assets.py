"""Stage 2: Download CDN assets and rewrite links to local paths."""

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

CDN_PATTERN = re.compile(r'https?://lms-cdn\.skillfactory\.ru/[^\s\)\]\"\']+')
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}
MAX_WORKERS = 4
TIMEOUT = 30


def url_to_local_name(url: str) -> str:
    """Generate unique local filename from URL."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    original_name = Path(path).name
    original_name = re.sub(r'[^\w.\-]', '_', original_name)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{url_hash}_{original_name}"


def collect_urls(vault_dir: Path) -> dict[str, list[Path]]:
    """Scan .md files for CDN URLs."""
    assets_dir = vault_dir / "_assets"
    url_map = {}
    for md_file in vault_dir.rglob('*.md'):
        if md_file.is_relative_to(assets_dir):
            continue
        try:
            content = md_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for match in CDN_PATTERN.finditer(content):
            url = match.group(0).rstrip('.,;:!?)>')
            url_map.setdefault(url, []).append(md_file)
    return url_map


def _download_one(url: str, dest: Path) -> tuple[str, bool, str]:
    if dest.exists() and dest.stat().st_size > 0:
        return (url, True, "cached")
    for _ in range(2):
        try:
            resp = requests.get(url, timeout=TIMEOUT, stream=True)
            if resp.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return (url, True, "")
            err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            err = str(e)
    return (url, False, err)


def rewrite_links(vault_dir: Path, url_to_filename: dict[str, str]) -> int:
    """Rewrite CDN URLs to Obsidian local format."""
    assets_dir = vault_dir / "_assets"
    files_changed = 0

    for md_file in vault_dir.rglob('*.md'):
        if md_file.is_relative_to(assets_dir):
            continue
        try:
            content = md_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        original = content
        for url, local_name in url_to_filename.items():
            if url not in content:
                continue
            ext = Path(local_name).suffix.lower()
            if ext in IMAGE_EXTS:
                content = re.sub(
                    r'!\[([^\]]*)\]\(' + re.escape(url) + r'\)',
                    f'![[{local_name}]]', content)
                content = content.replace(url, f'![[{local_name}]]')
            else:
                content = re.sub(
                    r'\[([^\]]*)\]\(' + re.escape(url) + r'\)',
                    lambda m: f'[[{local_name}|{m.group(1) or local_name}]]', content)
                content = content.replace(url, f'[[{local_name}]]')

        if content != original:
            md_file.write_text(content, encoding='utf-8')
            files_changed += 1
    return files_changed


def download_assets(vault_dir: Path):
    """Main entry: collect, download, rewrite."""
    assets_dir = vault_dir / "_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print("Scanning vault for CDN URLs...")
    url_map = collect_urls(vault_dir)
    print(f"  Found {len(url_map)} unique assets")

    if not url_map:
        print("Nothing to download.")
        return

    url_to_filename = {url: url_to_local_name(url) for url in url_map}
    tasks = [(url, assets_dir / fn) for url, fn in url_to_filename.items()]

    print(f"\nDownloading {len(tasks)} assets ({MAX_WORKERS} threads)...")
    success = cached = failed = 0
    total_size = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_download_one, url, dest): url for url, dest in tasks}
        done = 0
        for future in as_completed(futures):
            done += 1
            url, ok, err = future.result()
            if ok:
                if err == "cached":
                    cached += 1
                else:
                    success += 1
                total_size += (assets_dir / url_to_filename[url]).stat().st_size
            else:
                failed += 1
            if done % 50 == 0 or done == len(tasks):
                print(f"  [{done}/{len(tasks)}] ✓{success} ⊙{cached} ✗{failed}", flush=True)

    print(f"\n  New: {success}, Cached: {cached}, Failed: {failed}")
    print(f"  Total size: {total_size / 1024 / 1024:.1f} MB")

    print(f"\nRewriting links...")
    successful = {u: fn for u, fn in url_to_filename.items() if (assets_dir / fn).exists()}
    files_changed = rewrite_links(vault_dir, successful)
    print(f"  Updated {files_changed} files")
