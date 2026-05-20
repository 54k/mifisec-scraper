"""Shared fixtures for e2e tests."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def course_outline():
    with open(FIXTURES_DIR / "course_outline.json") as f:
        return json.load(f)


@pytest.fixture
def xblock_html():
    return (FIXTURES_DIR / "xblock_sample.html").read_text(encoding='utf-8')


@pytest.fixture
def kinescope_html():
    return (FIXTURES_DIR / "kinescope_embed.html").read_text(encoding='utf-8')


@pytest.fixture
def vault_dir(tmp_path):
    """Provides a temporary vault directory."""
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault
