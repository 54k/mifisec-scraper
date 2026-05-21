"""CLI wizard for MIFISEC scraper."""

import argparse
import json
import shutil
from pathlib import Path

from .auth import COOKIES_FILE
from .utils import COURSES, PROJECT_ROOT


def get_output_dir() -> Path:
    return PROJECT_ROOT / "vault"


def ask(prompt: str, default: str = 'y') -> bool:
    """Ask yes/no question. Repeats until valid input."""
    suffix = '[Y/n]' if default == 'y' else '[y/N]'
    while True:
        answer = input(f"  {prompt} {suffix}: ").strip().lower()
        if not answer:
            return default == 'y'
        if answer in ('y', 'yes', 'д', 'да'):
            return True
        if answer in ('n', 'no', 'н', 'нет'):
            return False
        print("  Введи y или n")


def choose(prompt: str, options: list[str]) -> list[int]:
    """Ask user to pick options by number. Returns list of chosen indices."""
    print(f"  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}) {opt}")
    print(f"    a) Всё")
    print()
    while True:
        answer = input("  Выбор (номера через запятую или 'a'): ").strip().lower()
        if answer in ('a', 'all', 'все', 'а'):
            return list(range(len(options)))
        try:
            indices = [int(x.strip()) - 1 for x in answer.split(',')]
            if all(0 <= i < len(options) for i in indices):
                return indices
        except ValueError:
            pass
        print(f"  Введи номера 1-{len(options)} через запятую или 'a'")


def ensure_cookies() -> bool:
    """Check cookies.json exists, guide user to create if not."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE) as f:
                data = json.load(f)
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


def run_stage1(output_dir: Path, tracks: list[str] | None = None):
    """Run Stage 1. If tracks specified, scrape only those."""
    from .auth import create_session
    from .scraper import scrape_main_course, scrape_track, write_index

    session = create_session()
    output_dir.mkdir(parents=True, exist_ok=True)

    if tracks is None:
        # All
        scrape_main_course(session, output_dir)
        scrape_track(session, output_dir, 'pentest')
        scrape_track(session, output_dir, 'compliance')
    else:
        if 'main' in tracks:
            scrape_main_course(session, output_dir)
        if 'pentest' in tracks:
            scrape_track(session, output_dir, 'pentest')
        if 'compliance' in tracks:
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
        if ask("Скачать/докачать лекции?", default='n'):
            # Ask mode
            print()
            print("  Режим:")
            print("    1) Докачать недостающее (к существующему)")
            print("    2) Полный перескач (удалит и скачает заново)")
            print()
            while True:
                mode = input("  Режим [1/2]: ").strip()
                if mode in ('1', '2'):
                    break
                print("  Введи 1 или 2")

            if mode == '2':
                # Ask what to wipe+rescrape
                options = [
                    f"Основной курс ({COURSES['main']['name']})",
                    f"Трек Пентест ({COURSES['pentest']['name']})",
                    f"Трек Комплаенс ({COURSES['compliance']['name']})",
                ]
                track_keys = ['main', 'pentest', 'compliance']
                indices = choose("Что перескачать с нуля?", options)
                selected = [track_keys[i] for i in indices]
                # Wipe selected tracks
                import shutil as _sh
                from .utils import SEMESTER_NAMES
                if 'main' in selected:
                    for sem_name in SEMESTER_NAMES.values():
                        sem_path = output_dir / sem_name
                        if sem_path.exists():
                            _sh.rmtree(sem_path)
                            print(f"    Удалён: {sem_name}/")
                if 'pentest' in selected:
                    p = output_dir / COURSES['pentest']['name']
                    if p.exists():
                        _sh.rmtree(p)
                        print(f"    Удалён: {COURSES['pentest']['name']}/")
                if 'compliance' in selected:
                    p = output_dir / COURSES['compliance']['name']
                    if p.exists():
                        _sh.rmtree(p)
                        print(f"    Удалён: {COURSES['compliance']['name']}/")
                run_stage1(output_dir, tracks=selected)
            else:
                # Докачать — выбор что именно
                options = [
                    f"Основной курс ({COURSES['main']['name']})",
                    f"Трек Пентест ({COURSES['pentest']['name']})",
                    f"Трек Комплаенс ({COURSES['compliance']['name']})",
                ]
                track_keys = ['main', 'pentest', 'compliance']
                indices = choose("Что докачать?", options)
                selected = [track_keys[i] for i in indices]
                run_stage1(output_dir, tracks=selected)
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
        n_assets = len(list(assets_dir.iterdir()))
        print(f"  ⚡ Assets уже скачаны ({n_assets} файлов)")
        if ask("Докачать/перекачать assets?", default='n'):
            print()
            print("  Режим:")
            print("    1) Докачать недостающие (пропустит существующие)")
            print("    2) Удалить всё и скачать заново")
            print()
            while True:
                mode = input("  Режим [1/2]: ").strip()
                if mode in ('1', '2'):
                    break
                print("  Введи 1 или 2")
            if mode == '2':
                import shutil as _sh
                _sh.rmtree(assets_dir)
                print(f"    Удалён: _assets/")
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
            n_videos = len(list(videos_dir.rglob('*.mp4')))
            print(f"  ⚡ Видео уже скачаны ({n_videos} файлов)")
            if ask("Докачать/перекачать видео?", default='n'):
                print()
                print("  Режим:")
                print("    1) Докачать недостающие (пропустит существующие)")
                print("    2) Удалить всё и скачать заново")
                print()
                while True:
                    mode = input("  Режим [1/2]: ").strip()
                    if mode in ('1', '2'):
                        break
                    print("  Введи 1 или 2")
                if mode == '2':
                    import shutil as _sh
                    _sh.rmtree(videos_dir)
                    print(f"    Удалён: _videos/")
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
    parser.add_argument('--track', type=str, choices=['main', 'pentest', 'compliance'],
                        action='append', help='Scrape specific track(s) only (Stage 1)')
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
        run_stage1(output_dir, tracks=args.track)
        run_stage2(output_dir)
        run_stage3(output_dir, quality=args.quality)
        return

    if args.stage:
        if args.stage == 1:
            run_stage1(output_dir, tracks=args.track)
        elif args.stage == 2:
            run_stage2(output_dir)
        elif args.stage == 3:
            run_stage3(output_dir, quality=args.quality, limit=args.limit)
        return

    # Default: guided wizard
    wizard(output_dir, quality=args.quality)


if __name__ == '__main__':
    main()
