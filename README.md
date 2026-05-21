# MIFISEC Course Scraper

Скрейпер курса "Безопасность информационных систем" (НИЯУ МИФИ × SkillFactory) в Obsidian vault.

## Quick Start

```bash
git clone https://github.com/54k/mifisec-scraper
cd mifisec-scraper
make install-global                   # доступен из любой папки
brew install ffmpeg                   # для видео (Stage 3)

# в любой папке:
mkdir ~/mifisec && cd ~/mifisec
cp /path/to/cookies.json .           # или wizard поможет создать
mifisec                               # интерактивный wizard
```

## Установка

### Глобально (рекомендуется)

```bash
make install-global   # или: pip3 install --break-system-packages -e .
```

После этого `mifisec` доступен из любой папки. Vault и cookies.json ищутся в **текущей директории**.

### В venv (для разработки)

```bash
make dev              # или: python -m venv .venv && .venv/bin/pip install -e ".[dev]"
source .venv/bin/activate
```

### Зависимости

```bash
brew install ffmpeg   # для видео (Stage 3)
```

## Cookies

Залогинься на https://student-lk.skillfactory.ru и получи cookies:

- **Wizard:** `mifisec` предложит вставить JSON прямо в терминал
- **Вручную:** `cp cookies.example.json cookies.json` → заполни из DevTools (F12 → Application → Cookies)
- **Cookie-Editor:** экспорт из расширения браузера (массив поддерживается)

## Использование

### Wizard (рекомендуется)

```bash
mifisec   # или: make wizard
```

Пошаговый гайд:
1. Проверяет/создаёт `cookies.json`
2. **Stage 1** — загружает список курсов из API, предлагает выбрать какие качать → markdown
3. **Stage 2** — картинки, PDF, PPTX → `_assets/`, перезаписывает CDN-ссылки на `![[file]]`
4. **Stage 3** — видео записи → `_videos/` (4 параллельных ffmpeg), встраивает `![[video.mp4]]` в заметки

На каждом этапе если данные уже есть — предлагает режим:
- **Докачать** — пропускает существующие, скачивает новое
- **Полный перескач** — удаляет и качает заново

Stage 1 динамически показывает все доступные курсы из enrollments API.
Stage 3 предлагает выбор качества (360p/480p/720p/1080p).
Можно прервать `Ctrl+C` и продолжить — всё idempotent.

### CLI

```bash
mifisec --all                        # всё без вопросов
mifisec --stage 1                    # лекции (все треки)
mifisec --stage 1 --track compliance # только комплаенс
mifisec --stage 1 --track pentest    # только пентест
mifisec --stage 2                    # assets + rewrite ссылок
mifisec --stage 3                    # видео + linking в заметки
mifisec --stage 3 --quality 480      # видео в 480p
mifisec --stage 1 --limit 5          # smoke test (5 юнитов)
mifisec --list-videos                # список 208 записей
mifisec --fix-graph                  # починить раскраску Graph View
mifisec --output /path/vault         # другая директория
```

### Makefile

```bash
make help           # все команды
make install-global # установить глобально (mifisec из любой папки)
make dev            # venv + install + pytest (для разработки)
make test           # 32 теста за 0.3с
make wizard         # интерактивный wizard
make scrape         # Stage 1: лекции (~4 мин, ~20 MB)
make assets         # Stage 2: картинки/PDF + rewrite (~1 мин, ~500 MB)
make videos         # Stage 3: видео + linking (~3 часа, ~10 GB)
make videos-480     # Stage 3: в 480p (~5 GB)
make all            # всё (1→2→3)
make smoke          # быстрый тест (5 юнитов)
make list-videos    # список записей
make link-videos    # перелинковать видео в заметки (без скачивания)
make fix-graph      # починить раскраску Graph View
make clean          # удалить vault, venv, кэши
```

## Stages: что делает каждый

### Stage 1: Лекции → Markdown

- Обращается к Open edX API (`/api/course_home/outline/`)
- Обходит дерево: курс → главы → секции → юниты
- Для каждого юнита: GET xblock HTML → парсинг → markdownify
- Создаёт Obsidian vault с:
  - Семестровыми папками (`Семестр 1/`, ..., `Семестр 4/`)
  - MOC-файлами дисциплин (навигационные хабы)
  - YAML frontmatter с тегами для Graph View
  - Wikilinks навигация: unit → section → MOC → semester → index
  - `.obsidian/graph.json` с цветовыми группами

### Stage 2: Assets → Offline

- Сканирует все `.md` на CDN-ссылки (`lms-cdn.skillfactory.ru`)
- Скачивает в `_assets/` (4 потока, без auth — CDN публичный)
- **Перезаписывает ссылки:** `![](https://cdn...)` → `![[hash_file.png]]`
- После Stage 2 картинки рендерятся в Obsidian оффлайн

### Stage 3: Видео → Vault

- Находит 208 записей занятий (Kinescope iframe в xblock)
- Получает HLS manifest (m3u8) с Referer bypass
- Скачивает через ffmpeg (copy, без перекодирования)
- **Линкует в заметки:** вставляет `![[video.mp4]]` в соответствующий `.md`
- Obsidian рендерит встроенный видеоплеер

## Структура vault

```
vault/
├── index.md                      ← точка входа
├── Семестр 1/                    ← 9 дисциплин
│   ├── Семестр 1.md              ← хаб семестра
│   └── 01. I. Криптография/
│       ├── I. Криптография.md    ← MOC дисциплины
│       └── 01. Модуль 1.../
│           ├── Модуль 1.md       ← агрегат секции
│           └── 01. Тема.md       ← отдельный урок
├── Семестр 2/ ... 4/
├── ДПО и факультативы/
├── Трек Пентест/
├── Трек Комплаенс/
├── _assets/                      ← картинки/документы (Stage 2)
├── _videos/                      ← записи занятий (Stage 3)
└── .obsidian/graph.json
```

## Graph View

| Цвет | Что |
|------|-----|
| Красный (крупный) | index — точка входа |
| Золотой | Семестровые хабы |
| Жёлтый | Дисциплины (MOC) |
| Синий | Семестр 1 |
| Зелёный | Семестр 2 |
| Оранжевый | Семестр 3 |
| Красный (мелкий) | Семестр 4 |
| Фиолетовый | ДПО |
| Розовый | Треки |

## Тесты

```bash
make test   # или: pytest -v
```

32 теста, 0.34с, без сети:
- Cookie loading (flat/array/missing)
- Sanitize, tags, semester detection
- Vault structure generation (mock HTTP)
- Wikilink resolution
- CDN URL collection + rewriting (images/docs)
- Video discovery (kinescope iframe → HLS manifest)
- Video linking (exact match, dedup, fallback to section, skip _assets)

## Структура кода

```
src/mifisec/          1073 строки
├── cli.py       (243) — wizard + argparse
├── scraper.py   (280) — Stage 1: Open edX → markdown
├── videos.py    (229) — Stage 3: Kinescope → mp4 + linking
├── assets.py    (140) — Stage 2: CDN → _assets/ + rewrite
├── utils.py     (128) — constants, helpers
└── auth.py       (50) — cookies, session
```

## FAQ

**Прервал скрипт, можно продолжить?** Да. `Ctrl+C` и запусти снова — пропустит скачанное.

**Cookies протухли?** Перелогинься, обнови `cookies.json`. JWT ~7 дней.

**Одногруппник дал архив, хочу докачать только комплаенс?**
```bash
mifisec --stage 1 --track compliance
mifisec --stage 2   # докачает новые assets
```

**Хочу всё с нуля?** Wizard → "Полный перескач" → выбрать треки. Или `make clean && make all`.

**Хочу только перелинковать видео?** `make link-videos`

**Obsidian не показывает цвета?** Закрой Graph View → `Cmd+P` → `Graph view: Open graph view`

**Картинки не видны?** `make assets` — скачает и подменит CDN-ссылки.

**Видео не играет в Obsidian?** Проверь что `.mp4` в `_videos/`. Obsidian рендерит `![[file.mp4]]` как inline player.

**OOM / terminated при видео?** Обнови пакет (`git pull && pip install -e .`) — фикс буферизации ffmpeg.
