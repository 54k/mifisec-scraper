"""Authentication and session management."""

import json
from pathlib import Path

import requests

from .utils import PROJECT_ROOT

COOKIES_FILE = PROJECT_ROOT / "cookies.json"

REQUIRED_COOKIES = ('sessionid', 'edx-jwt-cookie-header-payload', 'edx-jwt-cookie-signature')


def load_cookies(cookies_file: Path | None = None) -> dict:
    """Load cookies from JSON file. Supports flat dict and Cookie-Editor array."""
    path = cookies_file or COOKIES_FILE
    if not path.exists():
        print(f"ERROR: {path} not found!")
        print()
        print("Инструкция:")
        print("1. Залогинься на https://student-lk.skillfactory.ru/my-study")
        print("2. Открой DevTools (F12) → Application → Cookies → skillfactory.ru")
        print("3. Создай cookies.json:")
        print()
        print('  {')
        print('    "sessionid": "...",')
        print('    "edx-jwt-cookie-header-payload": "...",')
        print('    "edx-jwt-cookie-signature": "..."')
        print('  }')
        print()
        print("Или экспортируй через Cookie-Editor (поддерживается массив)")
        raise SystemExit(1)

    with open(path, 'r') as f:
        data = json.load(f)

    if isinstance(data, list):
        return {c['name']: c['value'] for c in data if c.get('name') in REQUIRED_COOKIES}
    return data


def create_session(cookies_file: Path | None = None) -> requests.Session:
    """Create authenticated requests session."""
    session = requests.Session()
    session.cookies.update(load_cookies(cookies_file))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    })
    return session
