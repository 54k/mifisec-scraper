"""Tests for mifisec.utils."""

from mifisec.utils import get_discipline_tag, get_semester, sanitize, tags_yaml


def test_sanitize_removes_special_chars():
    assert sanitize('file: "test"/ok') == 'file testok'


def test_sanitize_max_len():
    assert len(sanitize('a' * 200, max_len=50)) == 50


def test_sanitize_strips_whitespace():
    assert sanitize('  hello   world  ') == 'hello world'


def test_get_semester_roman():
    assert get_semester('I. Криптография') == '1'
    assert get_semester('II. Управление ИБ') == '2'
    assert get_semester('III. Компьютерная криминалистика') == '3'
    assert get_semester('III-IV. Социальная инженерия') == '3'
    assert get_semester('IV. Форензика') == '4'


def test_get_semester_dpo():
    assert get_semester('ДПО Блокчейн') == 'dpo'
    assert get_semester('Организационные встречи') == 'dpo'


def test_get_discipline_tag():
    assert get_discipline_tag('I. Криптография') == 'discipline/crypto'
    assert get_discipline_tag('III. Компьютерная криминалистика') == 'discipline/forensics'
    assert get_discipline_tag('Unknown course') == 'discipline/other'


def test_tags_yaml():
    result = tags_yaml(['semester/1', 'type/lesson'])
    assert 'tags:' in result
    assert '  - semester/1' in result
    assert '  - type/lesson' in result
