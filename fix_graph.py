#!/usr/bin/env python3
"""
Fix graph connectivity:
1. Create semester hub nodes
2. Rewrite index.md → semester hubs only
3. Semester hubs → discipline MOCs
4. MOCs already → sections → units (backlinks done)
"""

import re
from pathlib import Path

VAULT = Path(__file__).parent / "vault"

# Semester definitions
SEMESTERS = {
    '1': {
        'name': 'Семестр 1',
        'pattern': r'^I\.',
        'color_tag': 'semester/1',
    },
    '2': {
        'name': 'Семестр 2',
        'pattern': r'^II\.',
        'color_tag': 'semester/2',
    },
    '3': {
        'name': 'Семестр 3',
        'pattern': r'^III[\.\-]',
        'color_tag': 'semester/3',
    },
    '4': {
        'name': 'Семестр 4',
        'pattern': r'^IV\.',
        'color_tag': 'semester/4',
    },
    'dpo': {
        'name': 'ДПО и факультативы',
        'pattern': r'^ДПО|^Организ|^Записи консульт|^Выбор трека|^Научно-исслед|^Учебная практика$',
        'color_tag': 'track/dpo',
    },
}


def get_semester(chapter_name: str) -> str:
    """Determine which semester a chapter belongs to."""
    clean = re.sub(r'^\d+\.\s*', '', chapter_name)
    for sem_id, sem in SEMESTERS.items():
        if re.search(sem['pattern'], clean):
            return sem_id
    return 'dpo'


def main():
    # Gather chapters and their MOC files
    chapters_by_semester = {}

    for chapter_dir in sorted(VAULT.iterdir()):
        if not chapter_dir.is_dir() or chapter_dir.name.startswith(('.', '_')):
            continue

        chapter_name = re.sub(r'^\d+\.\s*', '', chapter_dir.name)
        sem_id = get_semester(chapter_name)

        # Find MOC file (it's the .md file directly in chapter_dir that has type/moc tag)
        moc_file = None
        for f in chapter_dir.glob('*.md'):
            content = f.read_text(encoding='utf-8')
            if 'type/moc' in content:
                moc_file = f
                break

        if moc_file is None:
            # Fallback - find any .md in chapter root
            mds = list(chapter_dir.glob('*.md'))
            if mds:
                moc_file = mds[0]

        if moc_file:
            if sem_id not in chapters_by_semester:
                chapters_by_semester[sem_id] = []
            chapters_by_semester[sem_id].append({
                'dir': chapter_dir,
                'name': chapter_name,
                'moc': moc_file,
                'moc_rel': f"{chapter_dir.name}/{moc_file.stem}",
            })

    # Create semester hub files
    print("Creating semester hubs...")
    semester_links = []

    for sem_id, sem_info in SEMESTERS.items():
        if sem_id not in chapters_by_semester:
            continue

        chapters = chapters_by_semester[sem_id]
        sem_name = sem_info['name']
        sem_tag = sem_info['color_tag']

        lines = [
            '---',
            f'semester: "{sem_name}"',
            'course: MIFISEC',
            'tags:',
            f'  - {sem_tag}',
            '  - type/semester-hub',
            'aliases:',
            f'  - "{sem_name}"',
            '---',
            '',
            f'# {sem_name}',
            '',
            '> **nav:** [[index|← Безопасность информационных систем]]',
            '',
        ]

        for ch in chapters:
            lines.append(f'- [[{ch["moc_rel"]}|{ch["name"]}]]')

        lines.append('')

        hub_file = VAULT / f'{sem_name}.md'
        hub_file.write_text('\n'.join(lines), encoding='utf-8')
        semester_links.append((sem_name, sem_name))
        print(f"  Created: {sem_name}.md ({len(chapters)} disciplines)")

    # Rewrite index.md — link only to semester hubs
    print("\nRewriting index.md...")
    index_lines = [
        '---',
        'course: MIFISEC',
        'university: НИЯУ МИФИ',
        'program: Безопасность информационных систем',
        'tags:',
        '  - type/index',
        'aliases:',
        '  - MIFISEC',
        '  - Безопасность информационных систем',
        '  - БИС',
        '---',
        '',
        '# Безопасность информационных систем',
        '',
        'Магистратура НИЯУ МИФИ x SkillFactory',
        '',
        '## Структура программы',
        '',
    ]

    for sem_id in ['1', '2', '3', '4', 'dpo']:
        if sem_id not in chapters_by_semester:
            continue
        sem = SEMESTERS[sem_id]
        count = len(chapters_by_semester[sem_id])
        index_lines.append(f'- [[{sem["name"]}]] ({count} дисциплин)')

    index_lines.extend(['', '## Треки', '',
        '- [[Трек Пентест]] *(отдельный курс)*',
        '- [[Трек Комплаенс]] *(отдельный курс)*',
        '',
    ])

    (VAULT / 'index.md').write_text('\n'.join(index_lines), encoding='utf-8')

    # Also update MOC files to link back to semester hub
    print("\nAdding semester backlinks to MOCs...")
    for sem_id, chapters in chapters_by_semester.items():
        sem_name = SEMESTERS[sem_id]['name']
        for ch in chapters:
            moc_file = ch['moc']
            content = moc_file.read_text(encoding='utf-8')
            # Replace existing nav or add one
            nav_line = f'> **nav:** [[{sem_name}|← {sem_name}]] · [[index|← Программа]]'
            if '> **nav:**' in content:
                content = re.sub(r'> \*\*nav:\*\*.*', nav_line, content)
            else:
                # Insert after frontmatter
                if '---' in content:
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        content = f'---{parts[1]}---\n{nav_line}\n{parts[2]}'
            moc_file.write_text(content, encoding='utf-8')

    # Create placeholder track files
    for track_name, track_course in [
        ('Трек Пентест', 'course-v1:SkillFactory+mifisec_pentest2023+FEB_2024'),
        ('Трек Комплаенс', 'course-v1:SkillFactory+mifisec_compliance2023+FEB_2024'),
    ]:
        track_file = VAULT / f'{track_name}.md'
        track_file.write_text(
            f'---\n'
            f'track: "{track_name}"\n'
            f'course_id: "{track_course}"\n'
            f'tags:\n'
            f'  - type/track-hub\n'
            f'aliases:\n'
            f'  - "{track_name}"\n'
            f'---\n\n'
            f'# {track_name}\n\n'
            f'> **nav:** [[index|← Программа]]\n\n'
            f'*Контент ещё не скачан. Запусти `scrape.py` с `COURSE_ID = "{track_course}"`*\n',
            encoding='utf-8'
        )
        print(f"  Created placeholder: {track_name}.md")

    # Update graph.json with better settings for hub-spoke layout
    import json
    graph_config = {
        "collapse-filter": False,
        "search": "",
        "showTags": False,
        "showAttachments": False,
        "hideUnresolved": False,
        "showOrphans": False,
        "collapse-color-groups": False,
        "colorGroups": [
            {"query": "tag:#type/index", "color": {"a": 1, "rgb": 16777215}},
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
        "textFadeMultiplier": -2,
        "nodeSizeMultiplier": 1.5,
        "lineSizeMultiplier": 0.8,
        "collapse-forces": False,
        "centerStrength": 0.6,
        "repelStrength": 8,
        "linkStrength": 1,
        "linkDistance": 40,
        "scale": 0.7,
        "close": False
    }

    graph_path = VAULT / '.obsidian' / 'graph.json'
    graph_path.parent.mkdir(exist_ok=True)
    graph_path.write_text(json.dumps(graph_config, indent=2), encoding='utf-8')
    print(f"\n  Updated graph.json")

    print("\nDone! Hierarchy: index → semesters → disciplines → modules → lessons")
    print("\nIMPORTANT: Close and reopen the vault in Obsidian to pick up graph.json colors.")
    print("If colors still don't show, manually add Groups in Graph View settings.")


if __name__ == '__main__':
    main()
