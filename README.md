# MIFISEC Course Scraper

Скрейпер курса "Безопасность информационных систем" (НИЯУ МИФИ × SkillFactory) в Obsidian vault.

## Quick Start

```bash
git clone <repo>
cd masters-course
make dev                        # venv + install
cp cookies.example.json cookies.json  # заполнить значения
mifisec                         # запустить wizard
```

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Для видео (Stage 3):
```bash
brew install ffmpeg  # macOS
```

## Cookies

Залогинься на https://student-lk.skillfactory.ru и получи cookies:

**Способ 1 — через wizard:** `mifisec` предложит вставить JSON прямо в терминал.

**Способ 2 — вручную:**
```bash
cp cookies.example.json cookies.json
# Заполни значения из DevTools (F12) → Application → Cookies → .skillfactory.ru
```

**Способ 3 — Cookie-Editor:** экспорт из расширения браузера (массив поддерживается).

## Запуск

### Wizard (рекомендуется)

```bash
mifisec
```

Проведёт по шагам:
1. Проверит/создаст cookies.json
2. **Stage 1** — скачает лекции → markdown (~20 мин)
3. **Stage 2** — скачает картинки/PDF → `_assets/`, перепишет ссылки на локальные (~3 мин)
4. **Stage 3** — скачает видео записи → `_videos/` (~3 часа)

Каждый этап спрашивает подтверждение. Уже скачанное автоматически пропускается.

### CLI (для автоматизации)

```bash
mifisec --all                   # всё без вопросов
mifisec --stage 1               # только лекции
mifisec --stage 2               # только картинки + перезапись ссылок
mifisec --stage 3               # только видео
mifisec --stage 3 --quality 480 # видео в 480p
mifisec --stage 1 --limit 5     # smoke test (5 юнитов)
mifisec --list-videos           # список видео без скачивания
```

### Makefile

```bash
make help       # все команды
make dev        # установка
make test       # тесты
make all        # скачать всё
make smoke      # быстрый тест
```

## Что происходит на каждом этапе

| Stage | Что делает | Результат |
|-------|-----------|-----------|
| 1 | Скачивает лекции, тесты, задания через API | Markdown-файлы с frontmatter и wikilinks |
| 2 | Скачивает картинки/PDF с CDN, **заменяет URL на локальные** | `_assets/` + ссылки `![[file.png]]` |
| 3 | Скачивает видео записи (Kinescope → ffmpeg → mp4) | `_videos/дисциплина/запись.mp4` |

После Stage 2 все картинки отображаются в Obsidian оффлайн — CDN-ссылки заменены на локальные файлы.

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
├── Трек Пентест/                 ← трек (отдельный курс)
├── Трек Комплаенс/
├── _assets/                      ← картинки/документы (Stage 2)
├── _videos/                      ← записи занятий (Stage 3)
└── .obsidian/graph.json          ← цвета для Graph View
```

## Graph View

| Цвет | Что |
|------|-----|
| Красный (крупный) | index |
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
pytest -v
```

## Структура кода

```
src/mifisec/
├── cli.py       ← wizard + argparse
├── auth.py      ← cookies, session
├── scraper.py   ← Stage 1: лекции → markdown
├── assets.py    ← Stage 2: CDN → _assets/ + rewrite
├── videos.py    ← Stage 3: Kinescope → _videos/
└── utils.py     ← constants, helpers
```

## FAQ

**Cookies протухли?** Перелогинься и обнови cookies.json (JWT ~7 дней).

**Vault уже есть, хочу обновить?** Wizard спросит "Перескачать лекции?" — ответь `y`.

**Хочу только пентест-трек?** `mifisec --stage 1` скачивает и основной и пентест.

**Obsidian не показывает цвета?** Закрой Graph View → `Cmd+P` → `Graph view: Open graph view`.

**Картинки не отображаются?** Запусти `mifisec --stage 2` — он скачает и подменит ссылки.
