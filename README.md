# TORO STORE — Stone Island Resell Platform

![TORO STORE](https://torostore.ru/brand-logo)

E-commerce платформа для реселла Stone Island с Telegram Mini App, админ-панелью и AI-помощником.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10, Flask, SQLAlchemy, SQLite |
| Frontend | Vanilla JS, Custom CSS (no frameworks) |
| Hosting | Beget.ru, Passenger WSGI |
| Bot | Telegram Bot API, Mini App (WebView) |
| AI | DeepSeek API (product descriptions, search) |
| Fonts | TT Rounds Neue, Saira Stencil One, JetBrains Mono |

## Features

### Каталог
- Серверный рендеринг карточек товаров
- Фильтрация по категориям, размерам, сезонам
- Поиск по артикулу и названию
- Сортировка: по умолчанию / дешевле / дороже
- Избранное (localStorage)
- Архив проданных товаров

### Карточка товара
- Галерея изображений со свайпом и зумом
- Информация: цена, размер, сезон, состояние, артикул
- Ссылка на Avito
- Дефекты с отдельной галереей

### Telegram Mini App
- `/stone/webapp` — версия для миниаппки
- Адаптивная вёрстка с учётом safe-area
- Полноэкранный режим и нативный скролл
- Интеграция: кнопка STORE в боте, deep-link на товары

### Админ-панель
Система управления товарами с сессионной аутентификацией. Полный набор инструментов для ведения каталога:

- **CRUD товаров** — создание, редактирование, удаление. Поддержка всех полей: цена, старая цена, скидка, размер, сезон, артикул, состояние, дефекты, категория, описание
- **Медиа** — загрузка фото на S3-совместимое хранилище (Selectel). До 8 фото на товар + отдельные фото дефектов
- **Архивация** — перевод проданных товаров в архив с ценой продажи
- **Бронирование** — отметка товаров как зарезервированных
- **Дропы** — создание неактивных товаров и ручной релиз в каталог
- **AI-помощник** — интеграция с DeepSeek: генерация описаний, поиск по каталогу через нейросеть
- **Статистика** — просмотры, избранное, источники трафика (сайт / вебапп)
- **Telegram-уведомления** — оповещения о новых заказах и взаимодействиях через бота

### Телеграм-бот (@torostore_bot)
- Вебхук с обработкой inline-кнопок
- Кнопка STORE в интерфейсе чата
- Deep-link на конкретные товары (`startapp=item_XXX`)
- Рассылка новых поступлений
- Модерация: проверка подписки на канал перед доступом

### Дашборд сотрудников
Отдельное приложение для внутреннего учёта:
- График работы, учёт выручки, закупа, прихода
- Голосовой ввод и AI-разбор для ревизий
- Генерация отчётов для печати

## Project Structure

```
server/torostore.ru/
└── app/
    ├── app.py                    # Flask entry point
    ├── db.py                     # SQLAlchemy init
    ├── models.py                 # Data models
    ├── passenger_wsgi.py         # Passenger config
    ├── middleware.py             # Auth, analytics
    ├── utils.py                  # Helpers
    ├── config.py                 # Constants
    ├── requirements.txt          # Python deps
    ├── stone/                    # Stone Island module
    │   ├── __init__.py
    │   ├── routes.py             # Blueprint
    │   ├── models.py             # StoneProduct model
    │   ├── middleware.py         # Admin auth
    │   ├── config.py             # BOT_TOKEN, etc
    │   ├── utils.py              # Image helpers
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
    │   └── stone_catalog.html    # Main template (3400+ lines)
    ├── static/                   # Static assets
    └── media/                    # Uploaded images
```

## Setup

```bash
cd server/torostore.ru/app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Environment variables (via .htaccess or env)

```
BOT_TOKEN_STONE     — Telegram bot token
DEEPSEEK_API_KEY    — DeepSeek API key
ADMIN_PASSWORD      — Admin panel password
S3_ACCESS_KEY       — S3 access key
S3_SECRET_KEY       — S3 secret key
BASE_URL            — Site base URL
```

### Run locally

```bash
flask run --port 5000
```

## Deployment

Deployed on shared hosting with Passenger (WSGI). Restart: `touch tmp/restart.txt`

## License

MIT
