# Secure config - secrets MUST be set as environment variables
import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Required secrets - fail if not set
def get_required_env(name):
    value = os.environ.get(name)
    if not value:
        sys.stderr.write(f"FATAL: Environment variable {name} is not set!\n")
        raise ValueError(f"Required environment variable {name} is not set")
    return value

def get_env(name, default=None):
    return os.environ.get(name, default)

# Telegram Bot
BOT_TOKEN = get_required_env('BOT_TOKEN')
ADMIN_CHAT_ID = get_required_env('ADMIN_CHAT_ID')
GROUP_CHAT_ID = get_required_env('GROUP_CHAT_ID')

# Алиасы для get_tokens эндпоинта — клиент ожидает именно такие имена
TELEGRAM_BOT_TOKEN = BOT_TOKEN
TELEGRAM_CHAT_ID = ADMIN_CHAT_ID

# App secrets
SECRET_KEY = get_required_env('SECRET_KEY')
ADMIN_PASSWORD = get_required_env('ADMIN_PASSWORD')

# Selectel (optional - only if server needs S3 access)
SELECTEL_ACCESS_KEY = get_env('SELECTEL_ACCESS_KEY', '')
SELECTEL_SECRET_KEY = get_env('SELECTEL_SECRET_KEY', '')

# Platega payment (required)
PLATEGA_MERCHANT_ID = get_required_env('PLATEGA_MERCHANT_ID')
PLATEGA_SECRET = get_required_env('PLATEGA_SECRET')
PLATEGA_API_URL = 'https://app.platega.io'

# Schedule screenshot chat (optional, defaults to GROUP_CHAT_ID)
SCHEDULE_CHAT_ID = get_env('SCHEDULE_CHAT_ID', GROUP_CHAT_ID)

# Download URL (optional)
DOWNLOAD_URL = get_env('DOWNLOAD_URL', '')

# VK (ВКонтакте) для отправки сообщений сотрудникам
VK_API_TOKEN = get_env('VK_API_TOKEN', '')
VK_USER_ID = get_env('VK_USER_ID', '')

# Tribute (optional)
TRIBUTE_API_KEY = get_env('TRIBUTE_API_KEY', '')

# Key config
KEY_LENGTH = 16
MAX_KEYS_PER_USER = 5
SESSION_TIMEOUT = 86400

# Типы ключей - используется в app.py
KEY_TYPES = {
    'test': {'days': 1},
    '2m': {'minutes': 2},
    '30d': {'days': 30},
    '180d': {'days': 180},
    '365d': {'days': 365},
    'permanent': {'days': None}
}

# Маппинг цен в рублях (для платежей)
PRICE_MAPPING = {
    1: 'test',
    700: '30d',
    3700: '180d',
    7700: '365d',
    10000: 'permanent'
}

# Цены в копеках (для админки)
KEY_PRICES = {
    'test': 0,
    '30d': 70000,
    '180d': 370000,
    '365d': 770000,
    'permanent': 1000000
}

SUBSCRIPTION_NAMES = {'тестовый': 'test', 'Пользователь': '30d', 'Полгода': '180d', 'Год': '365d', 'Навсегда': 'permanent'}