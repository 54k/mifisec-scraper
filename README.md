# MIFISEC Course Scraper

Скрейпер курса "Безопасность информационных систем" (НИЯУ МИФИ × SkillFactory) → Obsidian vault.

## Tutorial: первый запуск

```bash
# 1. Установка
git clone https://github.com/54k/mifisec-scraper
cd mifisec-scraper
make install-global
brew install ffmpeg

# 2. Подготовка (в любой папке)
mkdir ~/mifisec && cd ~/mifisec
cp /path/to/cookies.json .    # или wizard поможет создать

# 3. Запуск
mifisec
```

Wizard проведёт через все этапы: выбор курсов → лекции → картинки → видео.

## How-to guides

### Скачать только определённые курсы

```bash
mifisec --stage 1 --track pentest
mifisec --stage 1 --track compliance
```

### Скачать видео в низком качестве

```bash
mifisec --stage 3 --quality 360
```

### Докачать после прерывания

Просто запусти `mifisec` снова — пропустит скачанное.

### Починить раскраску Graph View

```bash
mifisec --fix-graph
# Закрой Obsidian → открой заново
```

### Перелинковать видео в заметки

```bash
make link-videos
```

### Одногруппник дал архив, нужен только комплаенс

```bash
cd /path/to/archive
mifisec --stage 1 --track compliance
mifisec --stage 2
```

### Полный перескач с нуля

```bash
make clean
mifisec
```

## Reference

### CLI

```bash
mifisec                              # интерактивный wizard
mifisec --all                        # всё без вопросов
mifisec --stage {1,2,3}              # конкретный этап
mifisec --stage 1 --track NAME       # конкретный курс (main/pentest/compliance)
mifisec --stage 3 --quality {360,480,720,1080}
mifisec --limit N                    # ограничить количество (для теста)
mifisec --list-videos                # список записей
mifisec --fix-graph                  # починить Graph View цвета
mifisec --output /path               # другая директория
```

### Makefile

```bash
make install-global  # mifisec доступен глобально
make dev             # venv для разработки
make test            # 32 теста, <1с
make wizard          # интерактивный wizard
make scrape          # Stage 1
make assets          # Stage 2
make videos          # Stage 3 (720p)
make videos-480      # Stage 3 (480p)
make all             # 1→2→3
make smoke           # 5 юнитов (быстрый тест)
make list-videos     # список записей
make link-videos     # перелинковать видео
make fix-graph       # починить Graph View
make clean           # удалить vault, venv
```

### Stages

| Stage | Что делает | Вход | Выход |
|-------|-----------|------|-------|
| 1 | Open edX API → markdown | cookies.json | vault с md-файлами, frontmatter, wikilinks |
| 2 | CDN assets → локальные файлы | vault/*.md с CDN-URL | `_assets/` + ссылки `![[file]]` |
| 3 | Kinescope → mp4 через ffmpeg | vault (для поиска записей) | `_videos/` + `![[video.mp4]]` в заметках |

### Структура vault

```
vault/
├── index.md
├── Семестр {1-4}/
│   ├── Семестр N.md              (hub)
│   └── NN. Discipline/
│       ├── Discipline.md         (MOC)
│       └── NN. Section/
│           ├── Section.md        (aggregate)
│           └── NN. Unit.md       (lesson)
├── Трек Пентест/
├── Трек Комплаенс/
├── _assets/                      (images, PDF, PPTX)
├── _videos/                      (mp4)
└── .obsidian/graph.json          (Graph View colors)
```

### Graph View цвета

| Цвет | Tag query | Что |
|------|-----------|-----|
| Красный (крупный) | `path:index` | Точка входа |
| Золотой | `tag:#type/semester-hub` | Семестры |
| Жёлтый | `tag:#type/moc` | Дисциплины |
| Синий | `tag:#semester/1` | Семестр 1 |
| Зелёный | `tag:#semester/2` | Семестр 2 |
| Оранжевый | `tag:#semester/3` | Семестр 3 |
| Красный | `tag:#semester/4` | Семестр 4 |
| Фиолетовый | `tag:#track/dpo` | ДПО |
| Розовый | `tag:#type/track-hub` | Треки |

### Структура кода

```
src/mifisec/
├── cli.py        — wizard + argparse
├── scraper.py    — Stage 1: Open edX → markdown
├── assets.py     — Stage 2: CDN → _assets/ + rewrite
├── videos.py     — Stage 3: Kinescope → _videos/ + linking
├── utils.py      — constants, helpers
└── auth.py       — cookies, session
```

### Cookies

Нужны 3 cookies с `.skillfactory.ru`:
- `sessionid`
- `edx-jwt-cookie-header-payload`
- `edx-jwt-cookie-signature`

Форматы: flat JSON dict или Cookie-Editor array export.

## Explanation

### Почему 3 стейджа?

Разный контент — разные паттерны доступа, размеры и failure modes. Текст (20 MB) доступен за 4 минуты, картинки (500 MB) за минуту, видео (10-50 GB) за часы. Разделение позволяет получить рабочий vault быстро и докачивать тяжёлый контент потом.

### Почему CDN без авторизации?

Open edX хранит assets на CDN с прямым доступом (без cookies). Видео на Kinescope требуют Referer-заголовок (`lms.skillfactory.ru`) для получения HLS-манифеста.

### Почему graph.json сбрасывается?

Obsidian перезаписывает `graph.json` при первом открытии Graph View. Скрейпер перезаписывает его при каждом запуске wizard. `--fix-graph` делает то же самое вручную.

### Почему нумерация внутри семестра?

API может отдавать chapters в разном порядке. Глобальная нумерация (1-30) создаёт дубликаты при повторных запусках. Нумерация внутри семестра (1-9 в Семестр 1) стабильна.

## Architecture decisions

- [ADR-0001: Three-stage pipeline](docs/decisions/0001-scraper-architecture.md)
- [ADR-0002: Dynamic enrollment discovery](docs/decisions/0002-dynamic-enrollment-discovery.md)
- [ADR-0003: Obsidian vault structure](docs/decisions/0003-obsidian-vault-structure.md)
