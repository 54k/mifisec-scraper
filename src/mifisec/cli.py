"""CLI wizard for MIFISEC scraper."""

import argparse
import json
import shutil
from pathlib import Path

from .auth import COOKIES_FILE
from .utils import PROJECT_ROOT


def get_output_dir() -> Path:
    return PROJECT_ROOT / "vault"


def ask(prompt: str, default: str = 'y') -> bool:
    """Ask yes/no question."""
    suffix = '[Y/n]' if default == 'y' else '[y/N]'
    answer = input(f"  {prompt} {suffix}: ").strip().lower()
    if not answer:
        return default == 'y'
    return answer in ('y', 'yes', 'д', 'да')


def ensure_cookies() -> bool:
    """Check cookies.json exists, guide user to create if not."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE) as f:
                data = json.load(f)
            # Validate
            if isinstance(data, list):
                names = {c.get('name') for c in data}
            else:
                names = set(data.keys())
            if 'sessionid' in names:
                print("  ✓ cookies.json найден")
                return True
        except (json.JSONDecodeError, KeyError):
            pass
        print("  ✗ cookies.json повреждён")

    print()
    print("  ┌─────────────────────────────────────────────────┐")
    print("  │  Нужен cookies.json для авторизации              │")
    print("  │                                                   │")
    print("  │  1. Залогинься: student-lk.skillfactory.ru        │")
    print("  │  2. F12 → Application → Cookies → skillfactory.ru │")
    print("  │  3. Скопируй 3 cookies (или Cookie-Editor export) │")
    print("  └─────────────────────────────────────────────────┘")
    print()
    print("  Формат cookies.json:")
    print('  {')
    print('    "sessionid": "...",')
    print('    "edx-jwt-cookie-header-payload": "...",')
    print('    "edx-jwt-cookie-signature": "..."')
    print('  }')
    print()

    # Try to accept paste
    if ask("Вставить cookies JSON прямо сейчас?"):
        print("  Вставь JSON и нажми Enter (или пустая строка для отмены):")
        lines = []
        while True:
            line = input()
            if not line and lines:
                break
            lines.append(line)

        raw = '\n'.join(lines).strip()
        if not raw:
            return False

        try:
            data = json.loads(raw)
            COOKIES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            print(f"\n  ✓ Сохранено: {COOKIES_FILE}")
            return True
        except json.JSONDecodeError as e:
            print(f"\n  ✗ Невалидный JSON: {e}")
            return False

    print(f"\n  Создай файл вручную: {COOKIES_FILE}")
    return False


def run_stage1(output_dir: Path):
    from .auth import create_session
    from .scraper import scrape_main_course, scrape_track, write_index

    session = create_session()
    output_dir.mkdir(parents=True, exist_ok=True)

    scrape_main_course(session, output_dir)
    scrape_track(session, output_dir, 'pentest')
    scrape_track(session, output_dir, 'compliance')
    write_index(output_dir)
    print("\n  ✓ Stage 1 complete — лекции скачаны")


def run_stage2(output_dir: Path):
    from .assets import download_assets

    download_assets(output_dir)
    print("\n  ✓ Stage 2 complete — картинки/PDF скачаны")


def run_stage3(output_dir: Path, quality: int = 720, limit: int = 0, list_only: bool = False):
    from .auth import create_session
    from .videos import download_videos

    session = create_session()
    download_videos(session, output_dir, quality=quality, limit=limit, list_only=list_only)
    print("\n  ✓ Stage 3 complete — видео скачаны")


def wizard(output_dir: Path, quality: int = 720):
    """Guided sequential wizard."""
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   MIFISEC Course Scraper — Wizard    ║")
    print("  ║   НИЯУ МИФИ × SkillFactory           ║")
    print("  ╚══════════════════════════════════════╝")
    print()

    # Step 0: cookies
    if not ensure_cookies():
        print("\n  Без cookies невозможно продолжить. Выход.")
        return

    # Step 1: lectures
    print()
    print("  ━━━ Stage 1: Лекции и материалы ━━━")
    print("  Скачивает все лекции, тесты, задания в Obsidian markdown.")
    print("  Время: ~20 минут, размер: ~20 MB")
    print()

    if (output_dir / 'index.md').exists():
        print("  ⚡ Vault уже существует")
        if ask("Перескачать лекции (перезапишет)?", default='n'):
            run_stage1(output_dir)
        else:
            print("  Пропущено")
    elif ask("Скачать лекции?"):
        run_stage1(output_dir)
    else:
        print("  Пропущено")
        return

    # Step 2: assets
    print()
    print("  ━━━ Stage 2: Картинки и документы ━━━")
    print("  Скачивает PNG/JPG/PDF/PPTX для оффлайн-просмотра.")
    print("  Время: ~3 минуты, размер: ~500 MB")
    print()

    assets_dir = output_dir / '_assets'
    if assets_dir.exists() and len(list(assets_dir.iterdir())) > 100:
        print("  ⚡ Assets уже скачаны")
        if ask("Перекачать assets?", default='n'):
            run_stage2(output_dir)
        else:
            print("  Пропущено")
    elif ask("Скачать картинки и документы?"):
        run_stage2(output_dir)
    else:
        print("  Пропущено")

    # Step 3: videos
    print()
    print("  ━━━ Stage 3: Видео записи занятий ━━━")
    print("  Скачивает записи лекций с Kinescope (нужен ffmpeg).")
    print(f"  Время: ~3 часа, размер: ~10 GB (при {quality}p)")
    print()

    if not shutil.which('ffmpeg'):
        print("  ⚠ ffmpeg не найден! Установи: brew install ffmpeg")
        print("  Пропущено")
    else:
        videos_dir = output_dir / '_videos'
        if videos_dir.exists() and len(list(videos_dir.rglob('*.mp4'))) > 10:
            print(f"  ⚡ Видео уже скачаны ({len(list(videos_dir.rglob('*.mp4')))} файлов)")
            if ask("Докачать/перекачать видео?", default='n'):
                run_stage3(output_dir, quality=quality)
            else:
                print("  Пропущено")
        elif ask("Скачать видео записи?", default='n'):
            run_stage3(output_dir, quality=quality)
        else:
            print("  Пропущено")

    # Done
    print()
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  ✓ Готово! Vault: {output_dir}")
    print("  Открой в Obsidian: File → Open folder as vault")
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog='mifisec',
        description='SkillFactory MIFISEC → Obsidian vault scraper',
    )
    parser.add_argument('--all', action='store_true', help='Run all stages non-interactively')
    parser.add_argument('--stage', type=int, choices=[1, 2, 3], help='Run specific stage')
    parser.add_argument('--quality', type=int, default=720, choices=[360, 480, 720, 1080],
                        help='Video quality (default: 720)')
    parser.add_argument('--limit', type=int, default=0, help='Limit items (for testing)')
    parser.add_argument('--list-videos', action='store_true', help='List videos without downloading')
    parser.add_argument('--output', type=str, default=None, help='Output directory (default: ./vault)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else get_output_dir()

    if args.list_videos:
        run_stage3(output_dir, list_only=True)
        return

    if args.all:
        if not ensure_cookies():
            return
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

    # Default: guided wizard
    wizard(output_dir, quality=args.quality)


if __name__ == '__main__':
    main()
