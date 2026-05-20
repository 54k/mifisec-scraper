#!/usr/bin/env python3
"""
Restructure vault: move discipline folders into semester directories.
"""

import re
import shutil
from pathlib import Path

VAULT = Path(__file__).parent / "vault"

# Which chapters go into which semester (by folder prefix number)
SEMESTER_MAP = {
    # Semester 1: chapters 01-09
    '01': '1', '02': '1', '03': '1', '04': '1', '05': '1',
    '06': '1', '07': '1', '08': '1', '09': '1',
    # Semester 2: chapters 10-13
    '10': '2', '11': '2', '12': '2', '13': '2',
    # Semester 3: chapters 14-21
    '14': '3', '15': '3', '16': '3', '17': '3', '18': '3',
    '19': '3', '20': '3', '21': '3',
    # Semester 4: chapters 22-24
    '22': '4', '23': '4', '24': '4',
    # DPO/org: chapters 25-30
    '25': 'dpo', '26': 'dpo', '27': 'dpo', '28': 'dpo', '29': 'dpo', '30': 'dpo',
}

SEMESTER_DIRS = {
    '1': 'Семестр 1',
    '2': 'Семестр 2',
    '3': 'Семестр 3',
    '4': 'Семестр 4',
    'dpo': 'ДПО и факультативы',
}


def main():
    # Create semester directories
    for sem_dir in SEMESTER_DIRS.values():
        (VAULT / sem_dir).mkdir(exist_ok=True)

    # Track moves for link fixing
    moves = {}  # old_prefix → new_prefix

    # Move chapter folders into semester dirs
    for chapter_dir in sorted(VAULT.iterdir()):
        if not chapter_dir.is_dir():
            continue
        if chapter_dir.name.startswith(('.', '_')):
            continue
        # Skip semester dirs themselves and track dirs
        if chapter_dir.name in SEMESTER_DIRS.values():
            continue
        if chapter_dir.name.startswith('Трек'):
            continue

        prefix = chapter_dir.name[:2]
        if prefix not in SEMESTER_MAP:
            continue

        sem_id = SEMESTER_MAP[prefix]
        sem_dir = SEMESTER_DIRS[sem_id]
        dest = VAULT / sem_dir / chapter_dir.name

        if dest.exists():
            print(f"  SKIP (exists): {chapter_dir.name}")
            continue

        old_path = chapter_dir.name
        new_path = f"{sem_dir}/{chapter_dir.name}"
        moves[old_path] = new_path

        shutil.move(str(chapter_dir), str(dest))
        print(f"  {old_path} → {new_path}")

    # Move semester hub .md files into their directories
    for sem_id, sem_dir in SEMESTER_DIRS.items():
        hub_file = VAULT / f"{sem_dir}.md"
        if hub_file.exists():
            dest = VAULT / sem_dir / f"{sem_dir}.md"
            shutil.move(str(hub_file), str(dest))
            moves[sem_dir] = f"{sem_dir}/{sem_dir}"
            print(f"  {sem_dir}.md → {sem_dir}/{sem_dir}.md")

    print(f"\nMoved {len(moves)} items. Fixing links...")

    # Fix all wikilinks in all .md files
    all_md = list(VAULT.rglob('*.md'))
    fixed_files = 0

    for md_file in all_md:
        content = md_file.read_text(encoding='utf-8')
        original = content

        for old_prefix, new_prefix in moves.items():
            # Fix [[old_prefix/...]] → [[new_prefix/...]]
            content = content.replace(f'[[{old_prefix}/', f'[[{new_prefix}/')
            content = content.replace(f'[[{old_prefix}|', f'[[{new_prefix}|')
            content = content.replace(f'[[{old_prefix}]]', f'[[{new_prefix}]]')

        if content != original:
            md_file.write_text(content, encoding='utf-8')
            fixed_files += 1

    print(f"Fixed links in {fixed_files} files.")
    print("\nDone! Sidebar structure:")
    for d in sorted(VAULT.iterdir()):
        if d.name.startswith('.'):
            continue
        if d.is_dir():
            children = len(list(d.iterdir()))
            print(f"  📁 {d.name}/ ({children} items)")
        else:
            print(f"  📄 {d.name}")


if __name__ == '__main__':
    main()
