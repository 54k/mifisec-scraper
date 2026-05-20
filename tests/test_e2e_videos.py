"""E2E test: Stage 3 video discovery and linking (no actual downloads)."""

from pathlib import Path
from unittest.mock import MagicMock

from mifisec.videos import (
    find_recording_verticals,
    get_hls_manifest,
    get_kinescope_url,
    link_videos_to_vault,
)


def _make_blocks_with_recordings():
    """Create a blocks dict that has Записи sections with verticals."""
    blocks = {
        'course': {'type': 'course', 'display_name': 'Test', 'children': ['ch1']},
        'ch1': {'type': 'chapter', 'display_name': 'I. Криптография', 'children': ['seq1', 'seq2']},
        'seq1': {
            'type': 'sequential',
            'display_name': 'Записи дисциплины "Криптография"',
            'children': ['vert1', 'vert2'],
        },
        'seq2': {
            'type': 'sequential',
            'display_name': 'Модуль 1. Ключи',
            'children': ['vert3'],
        },
        'vert1': {'type': 'vertical', 'display_name': 'Занятие 1. 05.09'},
        'vert2': {'type': 'vertical', 'display_name': 'Занятие 2. 07.09'},
        'vert3': {'type': 'vertical', 'display_name': 'Введение'},
    }
    return blocks


def test_find_recording_verticals():
    """Finds verticals only inside Записи sequentials."""
    blocks = _make_blocks_with_recordings()
    recs = find_recording_verticals(blocks)
    assert len(recs) == 2
    assert recs[0]['name'] == 'Занятие 1. 05.09'
    assert recs[1]['name'] == 'Занятие 2. 07.09'
    assert recs[0]['chapter'] == 'I. Криптография'


def test_find_recording_verticals_skips_non_recordings():
    """Non-Записи sequentials are not picked up."""
    blocks = _make_blocks_with_recordings()
    recs = find_recording_verticals(blocks)
    names = [r['name'] for r in recs]
    assert 'Введение' not in names


def test_get_kinescope_url_extracts_iframe():
    """Extracts kinescope URL from vertical page with iframe."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '''
    <html><body>
    <div class="xblock" data-block-type="html">
        <iframe src="https://kinescope.io/embed/abc123?externalid=1"></iframe>
    </div>
    </body></html>
    '''
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    url = get_kinescope_url(mock_session, 'block-v1:test')
    assert url == 'https://kinescope.io/embed/abc123?externalid=1'


def test_get_kinescope_url_returns_none_without_iframe():
    """Returns None when no kinescope iframe present."""
    mock_session = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '<html><body><div class="xblock" data-block-type="html"><p>No video</p></div></body></html>'
    mock_resp.raise_for_status = MagicMock()
    mock_session.get.return_value = mock_resp

    url = get_kinescope_url(mock_session, 'block-v1:test')
    assert url is None


def test_get_hls_manifest_from_fixture(kinescope_html):
    """Extracts m3u8 URL from kinescope embed HTML."""
    import responses

    embed_url = "https://kinescope.io/embed/test123"

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, embed_url, body=kinescope_html, status=200)
        m3u8 = get_hls_manifest(embed_url)

    assert m3u8 is not None
    assert 'master.m3u8' in m3u8
    assert 'expires=' in m3u8


def test_get_hls_manifest_forbidden():
    """Returns None when kinescope returns forbidden."""
    import responses

    embed_url = "https://kinescope.io/embed/blocked"

    with responses.RequestsMock() as rsps:
        rsps.add(responses.GET, embed_url, body="<html><title>Access forbidden</title></html>", status=200)
        m3u8 = get_hls_manifest(embed_url)

    assert m3u8 is None


# === Video linking tests ===


def test_link_videos_exact_match(vault_dir):
    """Links video to md file with matching name (stripped prefix)."""
    videos_dir = vault_dir / "_videos" / "I. Криптография"
    videos_dir.mkdir(parents=True)
    (videos_dir / "Занятие 1. 05.09.mp4").write_bytes(b'\x00' * 2048)

    # Create md file with numbered prefix
    rec_dir = vault_dir / "Семестр 1" / "05. I. Криптография" / "01. Записи"
    rec_dir.mkdir(parents=True)
    md_file = rec_dir / "01. Занятие 1. 05.09.md"
    md_file.write_text("---\ntags:\n  - type/lesson\n---\n\n# Занятие 1. 05.09\n\nContent\n")

    linked = link_videos_to_vault(vault_dir, videos_dir)
    assert linked == 1

    content = md_file.read_text()
    assert "![[Занятие 1. 05.09.mp4]]" in content


def test_link_videos_no_duplicate(vault_dir):
    """Doesn't insert embed twice on re-run."""
    videos_dir = vault_dir / "_videos" / "chapter"
    videos_dir.mkdir(parents=True)
    (videos_dir / "Лекция.mp4").write_bytes(b'\x00' * 2048)

    md_file = vault_dir / "01. Лекция.md"
    md_file.write_text("---\ntags:\n  - type/lesson\n---\n\n# Лекция\n\n![[Лекция.mp4]]\n\nText\n")

    linked = link_videos_to_vault(vault_dir, videos_dir)
    assert linked == 1  # counted as success (already linked)

    content = md_file.read_text()
    assert content.count("![[Лекция.mp4]]") == 1


def test_link_videos_falls_back_to_section_aggregate(vault_dir):
    """When no individual md matches, links to Записи section file."""
    videos_dir = vault_dir / "_videos" / "IV. ВКР"
    videos_dir.mkdir(parents=True)
    (videos_dir / "26.02.2025 Консультация.mp4").write_bytes(b'\x00' * 2048)

    # No individual unit file, but section aggregate exists
    sec_dir = vault_dir / "Семестр 4" / "23. IV. ВКР" / "02. записи консультаций"
    sec_dir.mkdir(parents=True)
    section_file = sec_dir / "записи консультаций.md"
    section_file.write_text("---\ntags:\n  - type/module\n---\n\n# записи консультаций\n\nАгрегат\n")

    linked = link_videos_to_vault(vault_dir, videos_dir)
    assert linked == 1

    content = section_file.read_text()
    assert "![[26.02.2025 Консультация.mp4]]" in content


def test_link_videos_skips_assets_dir(vault_dir):
    """Doesn't match files inside _assets/."""
    videos_dir = vault_dir / "_videos" / "chapter"
    videos_dir.mkdir(parents=True)
    (videos_dir / "Test.mp4").write_bytes(b'\x00' * 2048)

    assets_dir = vault_dir / "_assets"
    assets_dir.mkdir()
    (assets_dir / "01. Test.md").write_text("# Test\n")

    # No valid target
    linked = link_videos_to_vault(vault_dir, videos_dir)
    assert linked == 0
