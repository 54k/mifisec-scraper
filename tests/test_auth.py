"""Tests for mifisec.auth."""

import json
import tempfile
from pathlib import Path

from mifisec.auth import load_cookies


def test_load_cookies_flat():
    data = {
        "sessionid": "abc",
        "edx-jwt-cookie-header-payload": "def",
        "edx-jwt-cookie-signature": "ghi",
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)
    result = load_cookies(path)
    assert result == data
    path.unlink()


def test_load_cookies_array():
    data = [
        {"name": "sessionid", "value": "abc", "domain": ".skillfactory.ru"},
        {"name": "edx-jwt-cookie-header-payload", "value": "def", "domain": ".skillfactory.ru"},
        {"name": "edx-jwt-cookie-signature", "value": "ghi", "domain": ".skillfactory.ru"},
        {"name": "other_cookie", "value": "ignored", "domain": ".skillfactory.ru"},
    ]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)
    result = load_cookies(path)
    assert result == {
        "sessionid": "abc",
        "edx-jwt-cookie-header-payload": "def",
        "edx-jwt-cookie-signature": "ghi",
    }
    path.unlink()


def test_load_cookies_missing_file(capsys):
    try:
        load_cookies(Path("/nonexistent/cookies.json"))
    except SystemExit as e:
        assert e.code == 1
