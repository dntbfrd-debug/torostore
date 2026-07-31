<p align="center">
  <a href="#ru"><img src="https://img.shields.io/badge/RU-000000?style=flat-square&labelColor=000000&color=fd79a8"/></a>
  <a href="#en"><img src="https://img.shields.io/badge/EN-000000?style=flat-square&labelColor=000000&color=fd79a8"/></a>
</p>

<details open name="lang" id="ru">
<summary><b>🇷🇺 Русский</b></summary>

# TORO STORE

Реселл-платформа Stone Island с Telegram Mini App, админ-панелью и AI-помощником.

## Возможности

- **Каталог** — серверный рендеринг, фильтрация по категориям/размерам/сезонам, поиск по артикулу, избранное, архив проданных
- **Карточка товара** — галерея со свайпом и зумом, цена/размер/сезон/состояние/артикул, ссылка на Avito, галерея дефектов
- **Telegram Mini App** — адаптивная вёрстка с safe-area, полноэкранный режим, кнопка STORE в боте, deep-link на товары
- **Админ-панель** — CRUD товаров, загрузка фото на S3, архивация, бронирование, дропы с ручным релизом
- **AI-поиск** — DeepSeek для генерации описаний и умного поиска по каталогу
- **Статистика** — просмотры, избранное, источники трафика (сайт/вебапп)
- **Телеграм-бот** (@torostore_bot) — вебхук, inline-кнопки, рассылка новых поступлений, проверка подписки на канал
- **Дашборд сотрудников** — график, учёт выручки/закупа/прихода, голосовой ввод, AI-разбор, печатные отчёты

---

## Быстрый старт

```bash
cd app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

---

## Структура проекта

```
torostore/
├── app.py                    # Flask entry point
├── db.py                     # SQLAlchemy init
├── models.py                 # Data models
├── middleware.py             # Auth, analytics
├── utils.py                  # Helpers
├── config.py                 # Constants
├── requirements.txt          # Python deps
├── stone/                    # Stone Island module
│   ├── models.py             # StoneProduct model
│   ├── middleware.py         # Admin auth
│   ├── services/
│   │   └── telegram.py       # Bot webhook
│   └── routes_modules/
│       ├── catalog.py        # Page rendering
│       ├── api_public.py     # Public API
│       ├── admin_crud.py     # CRUD operations
│       ├── admin_ai.py       # DeepSeek integration
│       ├── admin_stats.py    # Analytics
│       ├── admin_media.py    # Image upload
│       └── seo.py            # Sitemap/robots
├── templates/
│   ├── stone_catalog.html    # Main template (3400+ lines)
│   ├── stone_admin.html
│   ├── stone_admin_login.html
│   └── stone_archive.html
├── static/                   # Static assets
└── media/                    # Uploaded images
```

---

## Технологии

- **Python 3.10**
- **Flask** + SQLAlchemy + SQLite
- **Vanilla JS** + Custom CSS (без фреймворков)
- **Telegram Bot API** + WebView Mini App
- **DeepSeek API** (чат-модель)
- **Passenger WSGI** (деплой)

---

## Контакты

- **Telegram:** [@rtmnklvch](https://t.me/rtmnklvch)
- **Сайт:** [torostore.ru](https://torostore.ru)
- **Бот:** [@torostore_bot](https://t.me/torostore_bot)

</details>

<details name="lang" id="en">
<summary><b>🇬🇧 English</b></summary>

# TORO STORE

Stone Island resell platform with Telegram Mini App, admin panel, and AI assistant.

## Features

- **Catalog** — server-side rendering, category/size/season filters, article search, favorites, sold archive
- **Product Card** — swipe gallery with zoom, price/size/season/condition/art, Avito link, defect gallery
- **Telegram Mini App** — adaptive layout with safe-area, fullscreen mode, STORE button in bot, deep-link to products
- **Admin Panel** — product CRUD, S3 photo upload, archive, reserve, drops with manual release
- **AI Search** — DeepSeek for description generation and smart catalog search
- **Analytics** — views, favorites, traffic source tracking (website/webapp)
- **Telegram Bot** (@torostore_bot) — webhook, inline buttons, new arrivals broadcast, channel subscription check
- **Employee Dashboard** — schedule, revenue/purchase/arrival tracking, voice input, AI parsing, printable reports

---

## Quick Start

```bash
cd app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

---

## Tech Stack

- **Python 3.10**
- **Flask** + SQLAlchemy + SQLite
- **Vanilla JS** + Custom CSS (no frameworks)
- **Telegram Bot API** + WebView Mini App
- **DeepSeek API** (chat model)
- **Passenger WSGI** (deployment)

---

## Contact

- **Telegram:** [@rtmnklvch](https://t.me/rtmnklvch)
- **Website:** [torostore.ru](https://torostore.ru)
- **Bot:** [@torostore_bot](https://t.me/torostore_bot)

</details>
