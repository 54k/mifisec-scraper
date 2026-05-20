"""CLI wizard for MIFISEC scraper."""

import argparse
import sys
from pathlib import Path

from .utils import PROJECT_ROOT


def get_output_dir() -> Path:
    return PROJECT_ROOT / "vault"


def interactive_menu():
    """Show interactive menu and return choice."""
    print()
    print("  MIFISEC Course Scraper")
    print("  ──────────────────────")
    print("  1) Скачать лекции (Stage 1, ~20 мин)")
    print("  2) Скачать картинки/PDF (Stage 2, ~3 мин)")
    print("  3) Скачать видео записи (Stage 3, ~3 часа)")
    print("  4) Всё (1 → 2 → 3)")
    print("  q) Выход")
    print()
    choice = input("  Выбор [1-4/q]: ").strip()
    return choice


def run_stage1(output_dir: Path):
    from .auth import create_session
    from .scraper import scrape_main_course, scrape_track, write_index

    session = create_session()
    output_dir.mkdir(parents=True, exist_ok=True)

    scrape_main_course(session, output_dir)
    scrape_track(session, output_dir, 'pentest')
    scrape_track(session, output_dir, 'compliance')
    write_index(output_dir)
    print("\n✓ Stage 1 complete")


def run_stage2(output_dir: Path):
    from .assets import download_assets

    download_assets(output_dir)
    print("\n✓ Stage 2 complete")


def run_stage3(output_dir: Path, quality: int = 720, limit: int = 0, list_only: bool = False):
    from .auth import create_session
    from .videos import download_videos

    session = create_session()
    download_videos(session, output_dir, quality=quality, limit=limit, list_only=list_only)
    print("\n✓ Stage 3 complete")


def main():
    parser = argparse.ArgumentParser(
        prog='mifisec',
        description='SkillFactory MIFISEC → Obsidian vault scraper',
    )
    parser.add_argument('--all', action='store_true', help='Run all stages (1→2→3)')
    parser.add_argument('--stage', type=int, choices=[1, 2, 3], help='Run specific stage')
    parser.add_argument('--quality', type=int, default=720, choices=[360, 480, 720, 1080],
                        help='Video quality (Stage 3, default: 720)')
    parser.add_argument('--limit', type=int, default=0, help='Limit items (for testing)')
    parser.add_argument('--list-videos', action='store_true', help='List videos without downloading')
    parser.add_argument('--output', type=str, default=None, help='Output directory (default: ./vault)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else get_output_dir()

    if args.list_videos:
        run_stage3(output_dir, list_only=True)
        return

    if args.all:
        run_stage1(output_dir)
        run_stage2(output_dir)
        run_stage3(output_dir, quality=args.quality)
        return

    if args.stage:
        if args.stage == 1:
            run_stage1(output_dir)
        elif args.stage == 2:
            run_stage2(output_dir)
        elif args.stage == 3:
            run_stage3(output_dir, quality=args.quality, limit=args.limit)
        return

    # Interactive mode
    while True:
        choice = interactive_menu()
        if choice == '1':
            run_stage1(output_dir)
        elif choice == '2':
            run_stage2(output_dir)
        elif choice == '3':
            run_stage3(output_dir, quality=args.quality)
        elif choice == '4':
            run_stage1(output_dir)
            run_stage2(output_dir)
            run_stage3(output_dir, quality=args.quality)
        elif choice in ('q', 'Q', ''):
            break
        else:
            print("  Неизвестный выбор")


if __name__ == '__main__':
    main()
