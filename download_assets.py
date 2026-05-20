#!/usr/bin/env python3
"""
Stage 2: Download all CDN assets and rewrite links to local paths.

Скачивает все картинки, PDF, PPTX и прочие файлы с lms-cdn.skillfactory.ru
в vault/_assets/ и переписывает ссылки в markdown на Obsidian-формат.

Usage: python3 download_assets.py
"""

import hashlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

VAULT = Path(__file__).parent / "vault"
ASSETS_DIR = VAULT / "_assets"
CDN_PATTERN = re.compile(r'https?://lms-cdn\.skillfactory\.ru/[^\s\)\]\"\']+')
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp'}
MAX_WORKERS = 4
TIMEOUT = 30


def collect_urls() -> dict[str, list[Path]]:
    """Scan all .md files and collect unique CDN URLs with their source files."""
    url_map = {}  # url → [files that reference it]
    for md_file in VAULT.rglob('*.md'):
        if md_file.is_relative_to(ASSETS_DIR):
            continue
        try:
            content = md_file.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for match in CDN_PATTERN.finditer(content):
            url = match.group(0).rstrip('.,;:!?)>')
            if url not in url_map:
                url_map[url] = []
            url_map[url].append(md_file)
    return url_map


def url_to_local_name(url: str) -> str:
    """Generate a unique local filename from a URL."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    original_name = Path(path).name
    # Clean filename
    original_name = re.sub(r'[^\w.\-]', '_', original_name)
    # Hash for uniqueness (first 8 chars)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{url_hash}_{original_name}"


def download_one(url: str, dest: Path) -> tuple[str, bool, str]:
    """Download a single URL to dest. Returns (url, success, error_msg)."""
    if dest.exists() and dest.stat().st_size > 0:
        return (url, True, "cached")

    for attempt in range(2):
        try:
            resp = requests.get(url, timeout=TIMEOUT, stream=True)
            if resp.status_code == 200:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return (url, True, "")
            else:
                err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            err = str(e)

    return (url, False, err)


def rewrite_links(url_to_filename: dict[str, str]):
    """Rewrite all CDN URLs in markdown files to Obsidian local format."""
    files_changed = 0

    for md_file in VAULT.rglob('*.md'):
        if md_file.is_relative_to(ASSETS_DIR):
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
            is_image = ext in IMAGE_EXTS

            if is_image:
                # ![alt](url) → ![[local_name]]
                # Also handle bare URLs in image syntax
                content = re.sub(
                    r'!\[([^\]]*)\]\(' + re.escape(url) + r'\)',
                    f'![[{local_name}]]',
                    content
                )
                # Handle src="url" leftover patterns (shouldn't exist but just in case)
                content = content.replace(url, f'![[{local_name}]]')
            else:
                # [text](url) → [[local_name|text]]
                def replace_doc_link(m):
                    text = m.group(1) or local_name
                    return f'[[{local_name}|{text}]]'

                content = re.sub(
                    r'\[([^\]]*)\]\(' + re.escape(url) + r'\)',
                    replace_doc_link,
                    content
                )
                # Bare URL remaining
                content = content.replace(url, f'[[{local_name}]]')

        if content != original:
            md_file.write_text(content, encoding='utf-8')
            files_changed += 1

    return files_changed


def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    print("Scanning vault for CDN URLs...")
    url_map = collect_urls()
    print(f"  Found {len(url_map)} unique assets")

    if not url_map:
        print("Nothing to download.")
        return

    # Prepare download tasks
    url_to_filename = {}
    tasks = []
    for url in url_map:
        local_name = url_to_local_name(url)
        url_to_filename[url] = local_name
        dest = ASSETS_DIR / local_name
        tasks.append((url, dest))

    # Download
    print(f"\nDownloading {len(tasks)} assets ({MAX_WORKERS} threads)...")
    success = 0
    cached = 0
    failed = 0
    errors = []
    total_size = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_one, url, dest): url for url, dest in tasks}
        done = 0
        for future in as_completed(futures):
            done += 1
            url, ok, err = future.result()
            if ok:
                if err == "cached":
                    cached += 1
                else:
                    success += 1
                dest = ASSETS_DIR / url_to_filename[url]
                total_size += dest.stat().st_size
            else:
                failed += 1
                errors.append((url, err))

            if done % 50 == 0 or done == len(tasks):
                print(f"  [{done}/{len(tasks)}] ✓{success} ⊙{cached} ✗{failed}", flush=True)

    print(f"\nDownload complete:")
    print(f"  New: {success}, Cached: {cached}, Failed: {failed}")
    print(f"  Total size: {total_size / 1024 / 1024:.1f} MB")

    if errors:
        print(f"\nFailed URLs ({len(errors)}):")
        for url, err in errors[:20]:
            print(f"  {err}: {url[:80]}")

    # Rewrite links
    print(f"\nRewriting links in markdown files...")
    # Only rewrite for successfully downloaded assets
    successful_urls = {url: fn for url, fn in url_to_filename.items()
                      if (ASSETS_DIR / fn).exists()}
    files_changed = rewrite_links(successful_urls)
    print(f"  Updated {files_changed} files")

    print(f"\nDone! Assets in: {ASSETS_DIR}")


if __name__ == "__main__":
    main()
