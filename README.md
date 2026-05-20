# MIFISEC Course Scraper

Скрейпер курса "Безопасность информационных систем" (НИЯУ МИФИ × SkillFactory) в Obsidian vault.

## Что делает

Скачивает с платформы SkillFactory (Open edX) все лекции, тесты и материалы и складывает в структурированный Obsidian vault:

```
vault/
├── index.md                  ← точка входа (красная нода)
├── Семестр 1/                ← 9 дисциплин
├── Семестр 2/                ← 4 дисциплины
├── Семестр 3/                ← 8 дисциплин
├── Семестр 4/                ← 3 дисциплины
├── ДПО и факультативы/
├── Трек Пентест/             ← отдельный курс
├── Трек Комплаенс/           ← (пустой на платформе)
└── .obsidian/graph.json      ← цвета для Graph View
```

Каждый файл содержит:
- YAML frontmatter с тегами для Graph View (семестр, дисциплина, тип)
- Навигационные backlinks (`> **nav:** [[← назад]]`)
- Чистый markdown с заголовками и LaTeX-формулами

## Требования

```bash
pip install requests beautifulsoup4 markdownify
```

Python 3.10+

## Запуск

### 1. Получить cookies

Залогинься на https://student-lk.skillfactory.ru/my-study и достань cookies одним из способов:

**Способ A — DevTools:**
1. F12 → Application → Cookies → `.skillfactory.ru`
2. Скопируй значения трёх cookies в `cookies.json`:

```json
{
  "sessionid": "1|abc...",
  "edx-jwt-cookie-header-payload": "eyJ...",
  "edx-jwt-cookie-signature": "xyz..."
}
```

**Способ B — Cookie-Editor (расширение браузера):**
1. Установи Cookie-Editor для Firefox/Chrome
2. На странице skillfactory нажми Export → JSON
3. Сохрани как `cookies.json` (скрипт поддерживает массив)

### 2. Запустить скрейпер

```bash
python3 scrape.py
```

Займёт ~20 минут (основной курс) + ~5 минут (трек пентест).

### 3. Открыть в Obsidian

1. Obsidian → Open folder as vault → выбрать папку `vault/`
2. Graph View: `Cmd+P` → `Graph view: Open graph view`
3. Цвета и layout подхватятся из `.obsidian/graph.json`

## Graph View — цвета

| Цвет | Что |
|------|-----|
| Красный (большой) | index — точка входа |
| Золотой | Семестровые хабы |
| Жёлтый | MOC дисциплин |
| Синий/тёмный | Семестр 1 |
| Зелёный | Семестр 2 |
| Оранжевый | Семестр 3 |
| Красный (мелкий) | Семестр 4 |
| Фиолетовый | ДПО |
| Розовый | Треки |

## Структура проекта

```
masters-course/
├── scrape.py           ← единственный скрипт
├── cookies.json        ← твои cookies (в .gitignore)
├── vault/              ← результат (в .gitignore)
├── .gitignore
└── README.md
```

## FAQ

**Cookies протухли?**
Перелогинься на skillfactory и обнови cookies.json. JWT живёт ~7 дней, sessionid дольше.

**Трек Комплаенс пустой?**
На платформе 0 глав — контент не выложен или курс неактивен.

**Хочу только один трек?**
Отредактируй `main()` в `scrape.py` — закомментируй ненужные `scrape_track()`.

**Obsidian не показывает цвета?**
Закрой Graph View tab → `Cmd+P` → `Graph view: Open graph view` (новый таб подхватит graph.json).
