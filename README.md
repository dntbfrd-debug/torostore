<p align="center">
  <a href="#ru"><img src="https://img.shields.io/badge/RU-000000?style=flat-square&labelColor=000000&color=fd79a8"/></a>
  <a href="#en"><img src="https://img.shields.io/badge/EN-000000?style=flat-square&labelColor=000000&color=fd79a8"/></a>
</p>

<details open id="ru">
<summary><b>🇷🇺 Русский</b></summary>

# TORO STORE — Stone Island Resell Platform

E-commerce платформа для реселла Stone Island с Telegram Mini App, админ-панелью и AI-помощником.

## Стек
| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, Flask, SQLAlchemy, SQLite |
| Frontend | Vanilla JS, Custom CSS (no frameworks) |
| Bot | Telegram Bot API, Mini App (WebView) |
| AI | DeepSeek API |

## Возможности

### Каталог
- Серверный рендеринг карточек, фильтрация по категориям/размерам/сезонам
- Поиск по артикулу, сортировка, избранное, архив

### Карточка товара
- Галерея со свайпом и зумом, цена/размер/сезон/состояние/артикул
- Ссылка на Avito, дефекты с отдельной галереей

### Telegram Mini App
- `/stone/webapp` — версия для миниаппки
- Адаптивная вёрстка с safe-area, полноэкранный режим
- Кнопка STORE в боте, deep-link на товары

### Админ-панель
- CRUD товаров, загрузка фото на S3, архивация, бронирование
- Дропы с ручным релизом, AI-поиск (DeepSeek)
- Статистика просмотров/избранного/источников
- Telegram-уведомления

### Телеграм-бот (@torostore_bot)
- Вебхук с inline-кнопками, рассылка новых поступлений
- Проверка подписки на канал

## Установка
```bash
cd app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

</details>

<details id="en">
<summary><b>🇬🇧 English</b></summary>

# TORO STORE — Stone Island Resell Platform

E-commerce platform for Stone Island resell with Telegram Mini App, admin panel, and AI assistant.

## Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, Flask, SQLAlchemy, SQLite |
| Frontend | Vanilla JS, Custom CSS |
| Bot | Telegram Bot API, Mini App (WebView) |
| AI | DeepSeek API |

## Features

### Catalog
- Server-side rendering, category/size/season filters
- Article search, sorting, favorites, archive

### Product Card
- Swipe gallery with zoom, price/size/season/condition/art
- Avito link, defect gallery

### Telegram Mini App
- Adaptive layout with safe-area, fullscreen mode
- STORE button in bot, deep-link to products

### Admin Panel
- CRUD, S3 photo upload, archive, reserve
- Drops with manual release, AI search (DeepSeek)
- Views/favorites/source analytics
- Telegram notifications

### Telegram Bot (@torostore_bot)
- Webhook with inline buttons, new arrivals broadcast
- Channel subscription check

## Setup
```bash
cd app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
flask run --port 5000
```

</details>
