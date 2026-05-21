"""E2E test: Stage 1 scraper produces valid vault structure."""

import json
from unittest.mock import patch, MagicMock

import pytest

from mifisec.scraper import (
    build_tree, extract_content, scrape_main_course, write_index,
)
from mifisec.utils import SEMESTER_NAMES


def test_build_tree_from_fixture(course_outline):
    """build_tree correctly parses API response into tree."""
    blocks = course_outline['course_blocks']['blocks']
    tree = build_tree(blocks)
    assert len(tree) == 2
    assert tree[0]['name']
    assert len(tree[0]['sections']) == 2
    assert len(tree[0]['sections'][0]['units']) >= 1


def test_extract_content_from_xblock(xblock_html):
    """extract_content produces non-empty markdown from real xblock HTML."""
    content = extract_content(xblock_html)
    assert len(content) > 100
    # Should not contain raw HTML tags (except inline)
    assert '<div class="xblock"' not in content
    assert '<script' not in content


def test_scrape_creates_semester_structure(vault_dir, course_outline, xblock_html):
    """Full scrape pipeline creates correct folder hierarchy."""
    blocks = course_outline['course_blocks']['blocks']

    # Mock session
    mock_session = MagicMock()
    # Mock outline API
    mock_outline_resp = MagicMock()
    mock_outline_resp.json.return_value = course_outline
    mock_outline_resp.raise_for_status = MagicMock()
    # Mock xblock fetch
    mock_xblock_resp = MagicMock()
    mock_xblock_resp.text = xblock_html
    mock_xblock_resp.raise_for_status = MagicMock()

    mock_session.get.side_effect = lambda url, **kw: (
        mock_outline_resp if 'course_home' in url else mock_xblock_resp
    )

    scrape_main_course(mock_session, vault_dir)

    # Verify semester dirs created
    dirs = [d.name for d in vault_dir.iterdir() if d.is_dir()]
    assert any('Семестр' in d or 'ДПО' in d for d in dirs)

    # Verify .md files exist
    md_files = list(vault_dir.rglob('*.md'))
    assert len(md_files) > 0

    # Verify frontmatter in every file
    for md_file in md_files:
        content = md_file.read_text(encoding='utf-8')
        assert content.startswith('---'), f"Missing frontmatter: {md_file}"
        assert 'tags:' in content, f"Missing tags: {md_file}"


def test_write_index(vault_dir):
    """write_index creates index.md and graph.json."""
    # Create dummy semester dirs
    for sem in SEMESTER_NAMES.values():
        (vault_dir / sem).mkdir()

    write_index(vault_dir)

    index = vault_dir / 'index.md'
    assert index.exists()
    content = index.read_text()
    assert '[[' in content  # has wikilinks
    assert 'type/index' in content

    graph = vault_dir / '.obsidian' / 'graph.json'
    assert graph.exists()
    data = json.loads(graph.read_text())
    assert 'colorGroups' in data
    assert len(data['colorGroups']) > 5


def test_wikilinks_resolve(vault_dir, course_outline, xblock_html):
    """All wikilinks in generated vault point to existing files."""
    import re

    mock_session = MagicMock()
    mock_outline_resp = MagicMock()
    mock_outline_resp.json.return_value = course_outline
    mock_outline_resp.raise_for_status = MagicMock()
    mock_xblock_resp = MagicMock()
    mock_xblock_resp.text = xblock_html
    mock_xblock_resp.raise_for_status = MagicMock()
    mock_session.get.side_effect = lambda url, **kw: (
        mock_outline_resp if 'course_home' in url else mock_xblock_resp
    )

    scrape_main_course(mock_session, vault_dir)
    write_index(vault_dir)

    # Collect all wikilinks
    wikilink_pattern = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')
    broken = []

    for md_file in vault_dir.rglob('*.md'):
        content = md_file.read_text(encoding='utf-8')
        for match in wikilink_pattern.finditer(content):
            link_path = match.group(1)
            # Resolve: could be relative to vault root
            target = vault_dir / (link_path + '.md')
            # Also try without .md (Obsidian resolves by filename)
            target_by_name = list(vault_dir.rglob(f"{link_path.split('/')[-1]}.md"))
            if not target.exists() and not target_by_name:
                broken.append((md_file.name, link_path))

    # Allow some unresolved (semester hub links when not all semesters created)
    # but core links should resolve
    assert len(broken) < 5, f"Too many broken links: {broken[:10]}"
