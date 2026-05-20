"""E2E test: Stage 3 video discovery (no actual downloads)."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from mifisec.videos import (
    find_recording_verticals,
    get_hls_manifest,
    get_kinescope_url,
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
