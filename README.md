# MIFISEC Course Scraper

Скрейпер курса "Безопасность информационных систем" (НИЯУ МИФИ × SkillFactory) в Obsidian vault.

## Установка

```bash
git clone <repo>
cd masters-course
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Требуется `ffmpeg` для скачивания видео:
```bash
brew install ffmpeg  # macOS
```

## Cookies

Залогинься на https://student-lk.skillfactory.ru и создай `cookies.json`:

```json
{
  "sessionid": "...",
  "edx-jwt-cookie-header-payload": "...",
  "edx-jwt-cookie-signature": "..."
}
```

Или экспортируй через Cookie-Editor (массив поддерживается).

## Использование

### Wizard (интерактивно)

```bash
mifisec
```

### CLI

```bash
mifisec --all                   # всё (лекции → картинки → видео)
mifisec --stage 1               # только лекции (~20 мин)
mifisec --stage 2               # только картинки/PDF (~3 мин)
mifisec --stage 3               # только видео (~3 часа, 720p)
mifisec --stage 3 --quality 480 # видео в 480p (экономия места)
mifisec --stage 1 --limit 5     # 5 юнитов (smoke test)
mifisec --list-videos           # список видео без скачивания
mifisec --output /path/to/vault # другая директория
```

## Что скачивается

| Stage | Что | Размер | Время |
|-------|-----|--------|-------|
| 1 | Лекции, тесты, материалы → markdown | ~20 MB | ~20 мин |
| 2 | Картинки, PDF, PPTX → `_assets/` | ~500 MB | ~3 мин |
| 3 | Видео записи занятий → `_videos/` | ~10 GB (720p) | ~3 часа |

## Структура vault

```
vault/
├── index.md                     ← точка входа
├── Семестр 1/                   ← 9 дисциплин
│   ├── Семестр 1.md             ← хаб семестра
│   └── 01. I. Адаптационный курс/
│       ├── I. Адаптационный курс.md  ← MOC дисциплины
│       └── 01. Модуль 1.../
│           ├── Модуль 1.md      ← агрегат секции
│           └── 01. Тема.md      ← отдельный урок
├── Семестр 2/ ... 4/
├── ДПО и факультативы/
├── Трек Пентест/
├── Трек Комплаенс/
├── _assets/                     ← картинки/документы (Stage 2)
├── _videos/                     ← записи занятий (Stage 3)
└── .obsidian/graph.json         ← цвета для Graph View
```

## Graph View

Открой vault в Obsidian → `Cmd+P` → `Graph view: Open graph view`.

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
pytest
```

## Структура кода

```
src/mifisec/
├── cli.py       ← entry point, wizard + argparse
├── auth.py      ← cookie loading, session
├── scraper.py   ← Stage 1: course → markdown
├── assets.py    ← Stage 2: CDN → _assets/
├── videos.py    ← Stage 3: Kinescope → _videos/
└── utils.py     ← shared constants, helpers
```
