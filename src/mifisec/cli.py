"""CLI wizard for MIFISEC scraper."""

import argparse
import json
import shutil
from pathlib import Path

from .auth import COOKIES_FILE
from .utils import COURSES


def get_output_dir() -> Path:
    return Path.cwd() / "vault"


def ask(prompt: str, default: str = 'y') -> bool:
    """Ask yes/no question. Repeats until valid input."""
    suffix = '[Y/n]' if default == 'y' else '[y/N]'
    while True:
        try:
            answer = input(f"  {prompt} {suffix}: ").strip().lower()
        except (UnicodeDecodeError, EOFError):
            print()
            return default == 'y'
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
        try:
            answer = input("  Выбор (номера через запятую или 'a'): ").strip().lower()
        except (UnicodeDecodeError, EOFError):
            print()
            return list(range(len(options)))
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
            try:
                line = input()
            except (UnicodeDecodeError, EOFError):
                break
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


def run_stage1(output_dir: Path, courses: list[dict] | None = None, force: bool = False):
    """Run Stage 1. courses = list of {id, name} dicts to scrape."""
    from .auth import create_session
    from .scraper import scrape_main_course, scrape_track, write_index
    from .utils import COURSES

    session = create_session()
    output_dir.mkdir(parents=True, exist_ok=True)

    if courses is None:
        scrape_main_course(session, output_dir, force=force)
        scrape_track(session, output_dir, 'pentest', force=force)
        scrape_track(session, output_dir, 'compliance', force=force)
    else:
        for course in courses:
            cid = course['id']
            # Known tracks use dedicated scraper
            if cid == COURSES['main']['id']:
                scrape_main_course(session, output_dir, force=force)
            elif cid == COURSES['pentest']['id']:
                scrape_track(session, output_dir, 'pentest', force=force)
            elif cid == COURSES['compliance']['id']:
                scrape_track(session, output_dir, 'compliance', force=force)
            else:
                # Generic course — scrape as track
                scrape_track(session, output_dir, cid, force=force)

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
    print("  Скачивает лекции, тесты, задания в Obsidian markdown.")
    print()

    # Fetch available courses dynamically
    from .auth import create_session as _create_session
    from .scraper import get_enrollments
    print("  Загрузка списка курсов...", end=' ', flush=True)
    try:
        _session = _create_session()
        enrollments = get_enrollments(_session)
        print(f"найдено {len(enrollments)}")
    except Exception as e:
        print(f"ошибка: {e}")
        enrollments = []

    if not enrollments:
        print("  Не удалось получить список курсов.")
        return

    if (output_dir / 'index.md').exists():
        print()
        print("  ⚡ Vault уже существует")
        print("    1) Докачать недостающее")
        print("    2) Удалить и скачать заново")
        print("    n) Пропустить")
        print()
        while True:
            try:
                mode = input("  Выбор [1/2/n]: ").strip().lower()
            except (UnicodeDecodeError, EOFError):
                mode = 'n'
            if mode in ('1', '2', 'n', 'no', 'н'):
                break
            print("  Введи 1, 2 или n")

        if mode in ('n', 'no', 'н'):
            print("  Пропущено")
        else:
            options = [f"{c['name']}" for c in enrollments]
            indices = choose("Что качать?", options)
            selected = [enrollments[i] for i in indices]

            if mode == '2':
                import shutil as _sh
                from .utils import SEMESTER_NAMES
                for course in selected:
                    if course['id'] == COURSES['main']['id']:
                        for sem_name in SEMESTER_NAMES.values():
                            sem_path = output_dir / sem_name
                            if sem_path.exists():
                                _sh.rmtree(sem_path)
                                print(f"    Удалён: {sem_name}/")
                    else:
                        # Derive dir name
                        cname = course['name']
                        p = output_dir / cname
                        if p.exists():
                            _sh.rmtree(p)
                            print(f"    Удалён: {cname}/")

            run_stage1(output_dir, courses=selected, force=(mode == '2'))
    elif ask("Скачать лекции?"):
        options = [f"{c['name']}" for c in enrollments]
        indices = choose("Что качать?", options)
        selected = [enrollments[i] for i in indices]
        run_stage1(output_dir, courses=selected)
    else:
        print("  Пропущено")
        return

    # Step 2: assets
    print()
    print("  ━━━ Stage 2: Картинки и документы ━━━")
    print("  Скачивает PNG/JPG/PDF/PPTX для оффлайн-просмотра.")
    print()

    assets_dir = output_dir / '_assets'
    if assets_dir.exists() and len(list(assets_dir.iterdir())) > 100:
        n_assets = len(list(assets_dir.iterdir()))
        print(f"  ⚡ Assets уже скачаны ({n_assets} файлов)")
        print("    1) Докачать недостающие")
        print("    2) Удалить и скачать заново")
        print("    n) Пропустить")
        print()
        while True:
            try:
                mode = input("  Выбор [1/2/n]: ").strip().lower()
            except (UnicodeDecodeError, EOFError):
                mode = 'n'
            if mode in ('1', '2', 'n', 'no', 'н'):
                break
            print("  Введи 1, 2 или n")
        if mode in ('n', 'no', 'н'):
            print("  Пропущено")
        else:
            if mode == '2':
                import shutil as _sh
                _sh.rmtree(assets_dir)
                print(f"    Удалён: _assets/")
            run_stage2(output_dir)
    elif ask("Скачать картинки и документы?"):
        run_stage2(output_dir)
    else:
        print("  Пропущено")

    # Step 3: videos
    print()
    print("  ━━━ Stage 3: Видео записи занятий ━━━")
    print("  Скачивает записи лекций с Kinescope (нужен ffmpeg).")
    print()

    if not shutil.which('ffmpeg'):
        print("  ⚠ ffmpeg не найден! Установи: brew install ffmpeg")
        print("  Пропущено")
    else:
        videos_dir = output_dir / '_videos'

        def _ask_quality() -> int:
            print()
            print("  Качество видео:")
            print("    1) 360p")
            print("    2) 480p")
            print("    3) 720p (рекомендуется)")
            print("    4) 1080p")
            print()
            q_map = {'1': 360, '2': 480, '3': 720, '4': 1080}
            while True:
                try:
                    q = input(f"  Качество [1-4, default=3]: ").strip()
                except (UnicodeDecodeError, EOFError):
                    return 720
                if not q:
                    return 720
                if q in q_map:
                    return q_map[q]
                print("  Введи 1-4")

        if videos_dir.exists() and len(list(videos_dir.rglob('*.mp4'))) > 10:
            n_videos = len(list(videos_dir.rglob('*.mp4')))
            print(f"  ⚡ Видео уже скачаны ({n_videos} файлов)")
            print("    1) Докачать недостающие")
            print("    2) Удалить и скачать заново")
            print("    n) Пропустить")
            print()
            while True:
                try:
                    mode = input("  Выбор [1/2/n]: ").strip().lower()
                except (UnicodeDecodeError, EOFError):
                    mode = 'n'
                if mode in ('1', '2', 'n', 'no', 'н'):
                    break
                print("  Введи 1, 2 или n")
            if mode in ('n', 'no', 'н'):
                print("  Пропущено")
            else:
                quality = _ask_quality()
                if mode == '2':
                    import shutil as _sh
                    _sh.rmtree(videos_dir)
                    print(f"    Удалён: _videos/")
                run_stage3(output_dir, quality=quality)
        else:
            print("    y) Скачать")
            print("    n) Пропустить")
            print()
            if ask("Скачать видео записи (208 лекций)?", default='n'):
                quality = _ask_quality()
                run_stage3(output_dir, quality=quality)
            else:
                print("  Пропущено")

    # Ensure graph.json is correct (Obsidian may overwrite it)
    from .utils import GRAPH_CONFIG
    import json as _json
    obsidian_dir = output_dir / '.obsidian'
    obsidian_dir.mkdir(exist_ok=True)
    (obsidian_dir / 'graph.json').write_text(_json.dumps(GRAPH_CONFIG, indent=2), encoding='utf-8')

    # Done
    print()
    print("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  ✓ Готово! Vault: {output_dir}")
    print("  Открой в Obsidian: File → Open folder as vault")
    print("  ⚠ Если граф без цветов: закрой Obsidian → открой заново → Graph View")
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
    parser.add_argument('--fix-graph', action='store_true', help='Reapply Graph View colors (fixes blank graph)')
    parser.add_argument('--output', type=str, default=None, help='Output directory (default: ./vault)')
    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else get_output_dir()

    if args.fix_graph:
        import json as _json
        from .utils import GRAPH_CONFIG
        obsidian_dir = output_dir / '.obsidian'
        obsidian_dir.mkdir(exist_ok=True)
        (obsidian_dir / 'graph.json').write_text(_json.dumps(GRAPH_CONFIG, indent=2), encoding='utf-8')
        print(f"  ✓ Graph View раскраска обновлена: {obsidian_dir / 'graph.json'}")
        print("  Закрой Obsidian → открой заново → Graph View")
        return

    if args.list_videos:
        run_stage3(output_dir, list_only=True)
        return

    if args.all:
        if not ensure_cookies():
            return
        run_stage1(output_dir, courses=[{'id': COURSES[t]['id'], 'name': COURSES[t]['name']} for t in args.track] if args.track else None)
        run_stage2(output_dir)
        run_stage3(output_dir, quality=args.quality)
        return

    if args.stage:
        if args.stage == 1:
            run_stage1(output_dir, courses=[{'id': COURSES[t]['id'], 'name': COURSES[t]['name']} for t in args.track] if args.track else None)
        elif args.stage == 2:
            run_stage2(output_dir)
        elif args.stage == 3:
            run_stage3(output_dir, quality=args.quality, limit=args.limit)
        return

    # Default: guided wizard
    try:
        wizard(output_dir, quality=args.quality)
    except KeyboardInterrupt:
        print("\n\n  Прервано. Vault сохранён, можно продолжить позже.")
        raise SystemExit(0)


if __name__ == '__main__':
    main()
