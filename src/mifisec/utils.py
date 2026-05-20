"""Shared utilities and constants."""

import re
from pathlib import Path

BASE_URL = "https://lms.skillfactory.ru"
PROJECT_ROOT = Path(__file__).parent.parent.parent

COURSES = {
    "main": {
        "id": "course-v1:SkillFactory+MIFISEC+SEP_2023",
        "name": "Безопасность информационных систем",
    },
    "pentest": {
        "id": "course-v1:SkillFactory+mifisec_pentest2023+FEB_2024",
        "name": "Трек Пентест",
        "tag": "track/pentest",
    },
    "compliance": {
        "id": "course-v1:SkillFactory+mifisec_compliance2023+FEB_2024",
        "name": "Трек Комплаенс",
        "tag": "track/compliance",
    },
}

SEMESTER_PATTERNS = [
    (r'^I\.', '1'),
    (r'^II\.', '2'),
    (r'^III[\.\-]', '3'),
    (r'^IV\.', '4'),
]

SEMESTER_NAMES = {
    '1': 'Семестр 1',
    '2': 'Семестр 2',
    '3': 'Семестр 3',
    '4': 'Семестр 4',
    'dpo': 'ДПО и факультативы',
}

DISCIPLINE_TAGS = {
    'Криптография': 'discipline/crypto',
    'Сети и системы': 'discipline/networks',
    'Защита в операционных системах': 'discipline/os-security',
    'Программная инженерия': 'discipline/programming',
    'Теоретические основы ИБ': 'discipline/theory',
    'Защищенные информационные системы': 'discipline/secure-systems',
    'Нормативно-правовое': 'discipline/compliance',
    'Технические средства защиты': 'discipline/tech-tools',
    'Разработка защищенных': 'discipline/secure-dev',
    'Управление информационной безопасностью': 'discipline/isms',
    'Мониторинг, аналитика': 'discipline/monitoring',
    'Технология построения защищенных': 'discipline/secure-architecture',
    'Социальная инженерия': 'discipline/social-engineering',
    'Формализованные модели': 'discipline/formal-models',
    'Искусственный интеллект': 'discipline/ai-security',
    'Компьютерная криминалистика': 'discipline/forensics',
    'Форензика': 'discipline/forensics',
    'Аттестация, сертификация': 'discipline/certification',
    'АСУ ТП': 'discipline/ics-security',
    'Адаптационный': 'type/intro',
    'блокчейн': 'discipline/blockchain',
}

GRAPH_CONFIG = {
    "collapse-filter": False,
    "search": "",
    "showTags": False,
    "showAttachments": False,
    "hideUnresolved": False,
    "showOrphans": False,
    "collapse-color-groups": False,
    "colorGroups": [
        {"query": "path:index", "color": {"a": 1, "rgb": 16711680}},
        {"query": "tag:#type/semester-hub", "color": {"a": 1, "rgb": 16766720}},
        {"query": "tag:#type/track-hub", "color": {"a": 1, "rgb": 16711935}},
        {"query": "tag:#type/moc", "color": {"a": 1, "rgb": 16776960}},
        {"query": "tag:#semester/1", "color": {"a": 1, "rgb": 4495783}},
        {"query": "tag:#semester/2", "color": {"a": 1, "rgb": 3329330}},
        {"query": "tag:#semester/3", "color": {"a": 1, "rgb": 16744448}},
        {"query": "tag:#semester/4", "color": {"a": 1, "rgb": 16729156}},
        {"query": "tag:#track/dpo", "color": {"a": 1, "rgb": 10494192}},
        {"query": "tag:#type/org", "color": {"a": 0.4, "rgb": 6710886}},
    ],
    "collapse-display": False,
    "showArrow": True,
    "textFadeMultiplier": -3,
    "nodeSizeMultiplier": 2.5,
    "lineSizeMultiplier": 0.5,
    "collapse-forces": False,
    "centerStrength": 0.25,
    "repelStrength": 18,
    "linkStrength": 0.8,
    "linkDistance": 120,
    "scale": 0.4,
    "close": False,
}


def sanitize(name: str, max_len: int = 80) -> str:
    """Clean string for use as filename."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len]


def get_semester(chapter_name: str) -> str:
    """Determine semester ID from chapter name."""
    for pattern, sem_id in SEMESTER_PATTERNS:
        if re.search(pattern, chapter_name):
            return sem_id
    return 'dpo'


def get_discipline_tag(chapter_name: str) -> str:
    """Get discipline tag from chapter name."""
    for pattern, tag in DISCIPLINE_TAGS.items():
        if pattern.lower() in chapter_name.lower():
            return tag
    return 'discipline/other'


def tags_yaml(tags: list[str]) -> str:
    """Format tags as YAML frontmatter block."""
    lines = ['tags:']
    for t in tags:
        lines.append(f'  - {t}')
    return '\n'.join(lines)
