"""E2E test: Stage 2 asset discovery and link rewriting."""

import re

import pytest

from mifisec.assets import collect_urls, rewrite_links, url_to_local_name


def test_url_to_local_name_unique():
    """Different URLs produce different local names."""
    url1 = "https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc123/image1.png"
    url2 = "https://lms-cdn.skillfactory.ru/assets/courseware/v1/def456/image1.png"
    name1 = url_to_local_name(url1)
    name2 = url_to_local_name(url2)
    assert name1 != name2
    assert name1.endswith('.png')
    assert name2.endswith('.png')


def test_url_to_local_name_sanitized():
    """Local names don't contain unsafe chars."""
    url = "https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/Файл (1).png"
    name = url_to_local_name(url)
    assert '(' not in name
    assert ' ' not in name
    assert name.endswith('.png')


def test_collect_urls_finds_cdn_links(vault_dir):
    """collect_urls finds CDN URLs in markdown files."""
    # Create a sample md file with CDN links
    md_file = vault_dir / "test.md"
    md_file.write_text(
        "# Test\n"
        "![img](https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/image.png)\n"
        "[doc](https://lms-cdn.skillfactory.ru/assets/courseware/v1/def/file.pdf)\n"
        "No CDN here: https://example.com/other.png\n"
    )
    urls = collect_urls(vault_dir)
    assert len(urls) == 2
    assert any('image.png' in u for u in urls)
    assert any('file.pdf' in u for u in urls)


def test_collect_urls_ignores_assets_dir(vault_dir):
    """collect_urls skips files inside _assets/."""
    assets_dir = vault_dir / "_assets"
    assets_dir.mkdir()
    (assets_dir / "index.md").write_text(
        "https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/skip.png"
    )
    (vault_dir / "real.md").write_text(
        "![](https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/keep.png)"
    )
    urls = collect_urls(vault_dir)
    assert len(urls) == 1
    assert any('keep.png' in u for u in urls)


def test_rewrite_links_images(vault_dir):
    """rewrite_links converts image URLs to Obsidian format."""
    md_file = vault_dir / "lesson.md"
    cdn_url = "https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/diagram.png"
    md_file.write_text(f"# Lesson\n\n![Схема]({cdn_url})\n")

    url_to_filename = {cdn_url: "a1b2c3d4_diagram.png"}
    changed = rewrite_links(vault_dir, url_to_filename)

    assert changed == 1
    content = md_file.read_text()
    assert cdn_url not in content
    assert "![[a1b2c3d4_diagram.png]]" in content


def test_rewrite_links_documents(vault_dir):
    """rewrite_links converts document URLs to Obsidian wikilinks."""
    md_file = vault_dir / "lesson.md"
    cdn_url = "https://lms-cdn.skillfactory.ru/assets/courseware/v1/abc/lecture.pdf"
    md_file.write_text(f"# Lesson\n\n[Презентация]({cdn_url})\n")

    url_to_filename = {cdn_url: "e5f6g7h8_lecture.pdf"}
    changed = rewrite_links(vault_dir, url_to_filename)

    assert changed == 1
    content = md_file.read_text()
    assert cdn_url not in content
    assert "[[e5f6g7h8_lecture.pdf|Презентация]]" in content


def test_rewrite_leaves_no_cdn_urls(vault_dir):
    """After rewrite, no CDN URLs remain in vault."""
    # Create multiple files with CDN links
    urls = {
        "https://lms-cdn.skillfactory.ru/assets/courseware/v1/a/img1.png": "aa_img1.png",
        "https://lms-cdn.skillfactory.ru/assets/courseware/v1/b/img2.jpg": "bb_img2.jpg",
        "https://lms-cdn.skillfactory.ru/assets/courseware/v1/c/doc.pdf": "cc_doc.pdf",
    }
    for i, (url, _) in enumerate(urls.items()):
        (vault_dir / f"file{i}.md").write_text(f"Content: ![x]({url})\n")

    rewrite_links(vault_dir, urls)

    # Check no CDN URLs remain
    cdn_pattern = re.compile(r'https?://lms-cdn\.skillfactory\.ru')
    for md_file in vault_dir.rglob('*.md'):
        content = md_file.read_text()
        assert not cdn_pattern.search(content), f"CDN URL remains in {md_file.name}"
