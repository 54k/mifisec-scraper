#!/usr/bin/env python3
"""
Fix vault structure for better Obsidian Graph View:
- Rename _section.md → meaningful name
- Rename _MOC.md → chapter name
- Add tags for color grouping (semester, track, type)
- Add backlinks (unit → section → chapter → index)
"""

import re
import shutil
from pathlib import Path

VAULT = Path(__file__).parent / "vault"

# Tag mapping: chapter name patterns → tags
SEMESTER_TAGS = {
    r'^I\.': 'semester/1',
    r'^II\.': 'semester/2',
    r'^III\.': 'semester/3',
    r'^III-IV\.': 'semester/3-4',
    r'^IV\.': 'semester/4',
    r'^ДПО': 'track/dpo',
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
    'Учебная практика': 'type/practice',
    'Научно-исследовательская': 'type/research',
    'Выпускная квалификационная': 'type/thesis',
    'Оценка эффективности': 'discipline/project-mgmt',
    'блокчейн': 'discipline/blockchain',
    'Организационные встречи': 'type/org',
    'Записи консультаций': 'type/org',
    'Выбор трека': 'type/org',
}

CONTENT_TYPE_TAGS = {
    r'Тестирование': 'content/test',
    r'Лабораторная': 'content/lab',
    r'Практическ': 'content/practice',
    r'Записи': 'content/recordings',
    r'Силлабус': 'content/syllabus',
    r'Курсовая': 'content/coursework',
    r'Итоги модуля': 'content/summary',
    r'Обратная связь': 'content/feedback',
}


def get_semester_tag(chapter_name: str) -> str:
    for pattern, tag in SEMESTER_TAGS.items():
        if re.search(pattern, chapter_name):
            return tag
    return 'semester/other'


def get_discipline_tag(chapter_name: str) -> str:
    for pattern, tag in DISCIPLINE_TAGS.items():
        if pattern.lower() in chapter_name.lower():
            return tag
    return 'discipline/other'


def get_content_tags(name: str) -> list[str]:
    tags = []
    for pattern, tag in CONTENT_TYPE_TAGS.items():
        if re.search(pattern, name, re.IGNORECASE):
            tags.append(tag)
    return tags


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:80]


def update_frontmatter(content: str, updates: dict) -> str:
    """Add/update fields in YAML frontmatter."""
    if not content.startswith('---'):
        # No frontmatter, add one
        fm_lines = ['---']
        for k, v in updates.items():
            if isinstance(v, list):
                fm_lines.append(f'{k}:')
                for item in v:
                    fm_lines.append(f'  - {item}')
            else:
                fm_lines.append(f'{k}: "{v}"')
        fm_lines.append('---')
        fm_lines.append('')
        return '\n'.join(fm_lines) + content

    # Parse existing frontmatter
    parts = content.split('---', 2)
    if len(parts) < 3:
        return content

    fm = parts[1]
    body = parts[2]

    # Add new fields
    for k, v in updates.items():
        if k not in fm:
            if isinstance(v, list):
                fm += f'\n{k}:'
                for item in v:
                    fm += f'\n  - {item}'
            else:
                fm += f'\n{k}: "{v}"'

    return f'---{fm}\n---{body}'


def add_backlink(content: str, link_text: str) -> str:
    """Add a navigation backlink after frontmatter."""
    if '---' in content:
        parts = content.split('---', 2)
        if len(parts) >= 3:
            nav = f'\n> **nav:** {link_text}\n'
            return f'---{parts[1]}---{nav}{parts[2]}'
    return content


def main():
    print("Fixing vault for Graph View...")

    # Track renames to update links
    renames = {}  # old_stem → new_stem

    # === Pass 1: Rename files and add tags ===
    for chapter_dir in sorted(VAULT.iterdir()):
        if not chapter_dir.is_dir() or chapter_dir.name.startswith('_'):
            continue

        chapter_name = re.sub(r'^\d+\.\s*', '', chapter_dir.name)
        sem_tag = get_semester_tag(chapter_name)
        disc_tag = get_discipline_tag(chapter_name)

        # Rename _MOC.md → chapter name
        moc_file = chapter_dir / '_MOC.md'
        if moc_file.exists():
            new_moc_name = f"{sanitize_filename(chapter_name)}.md"
            new_moc = chapter_dir / new_moc_name
            content = moc_file.read_text(encoding='utf-8')
            content = update_frontmatter(content, {
                'tags': [sem_tag, disc_tag, 'type/moc'],
                'aliases': [chapter_name],
            })
            new_moc.write_text(content, encoding='utf-8')
            moc_file.unlink()
            renames[f"{chapter_dir.name}/_MOC"] = f"{chapter_dir.name}/{new_moc_name[:-3]}"
            print(f"  MOC: {chapter_dir.name}/_MOC → {new_moc_name}")

        # Process sections
        for section_dir in sorted(chapter_dir.iterdir()):
            if not section_dir.is_dir():
                continue

            section_name = re.sub(r'^\d+\.\s*', '', section_dir.name)

            # Rename _section.md
            section_file = section_dir / '_section.md'
            if section_file.exists():
                new_sec_name = f"{sanitize_filename(section_name)}.md"
                new_sec = section_dir / new_sec_name
                content = section_file.read_text(encoding='utf-8')

                # Determine content type tags
                ctags = get_content_tags(section_name)
                all_tags = [sem_tag, disc_tag] + ctags
                if not ctags:
                    all_tags.append('type/module')

                content = update_frontmatter(content, {
                    'tags': all_tags,
                    'aliases': [section_name],
                })

                # Add backlink to chapter MOC
                moc_link = f"[[{chapter_dir.name}/{sanitize_filename(chapter_name)}|← {chapter_name}]]"
                content = add_backlink(content, moc_link)

                new_sec.write_text(content, encoding='utf-8')
                section_file.unlink()
                old_key = f"{chapter_dir.name}/{section_dir.name}/_section"
                new_key = f"{chapter_dir.name}/{section_dir.name}/{new_sec_name[:-3]}"
                renames[old_key] = new_key
                print(f"  Section: {section_dir.name}/_section → {new_sec_name}")

            # Process individual unit files
            for unit_file in sorted(section_dir.glob('*.md')):
                if unit_file.name.startswith('_'):
                    continue
                # Skip the newly renamed section file
                if unit_file.name == f"{sanitize_filename(section_name)}.md":
                    continue

                content = unit_file.read_text(encoding='utf-8')
                unit_name = re.sub(r'^\d+\.\s*', '', unit_file.stem)
                ctags = get_content_tags(unit_name)
                all_tags = [sem_tag, disc_tag] + ctags
                if not ctags:
                    all_tags.append('type/lesson')

                content = update_frontmatter(content, {'tags': all_tags})

                # Add backlink to section
                sec_link_name = sanitize_filename(section_name)
                sec_link = f"[[{chapter_dir.name}/{section_dir.name}/{sec_link_name}|← {section_name}]]"
                content = add_backlink(content, sec_link)

                unit_file.write_text(content, encoding='utf-8')

    # === Pass 2: Fix links in index.md ===
    index_file = VAULT / 'index.md'
    if index_file.exists():
        content = index_file.read_text(encoding='utf-8')
        content = update_frontmatter(content, {
            'tags': ['type/index'],
            'aliases': ['MIFISEC', 'Безопасность информационных систем'],
        })
        # Fix _section links
        for old, new in renames.items():
            content = content.replace(old, new)
        index_file.write_text(content, encoding='utf-8')
        print(f"\n  Updated index.md with {len(renames)} renamed links")

    # === Pass 3: Fix links in MOC files ===
    for chapter_dir in sorted(VAULT.iterdir()):
        if not chapter_dir.is_dir() or chapter_dir.name.startswith('_'):
            continue
        for md_file in chapter_dir.glob('*.md'):
            content = md_file.read_text(encoding='utf-8')
            changed = False
            for old, new in renames.items():
                if old in content:
                    content = content.replace(old, new)
                    changed = True
            if changed:
                md_file.write_text(content, encoding='utf-8')

    print(f"\nDone! Renamed {len(renames)} files.")
    print("\nGraph View tips:")
    print("  - Groups → add color rules by tag:")
    print("    semester/1 = blue, semester/2 = green, semester/3 = orange, semester/4 = red")
    print("    type/moc = large yellow, type/index = largest white")
    print("  - Filters → toggle 'content/feedback' and 'content/recordings' off for cleaner view")
    print("  - Display → show tags, increase text fade threshold")


if __name__ == '__main__':
    main()
