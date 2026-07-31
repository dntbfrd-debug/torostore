import os

BOT_TOKEN_STONE = os.environ.get('BOT_TOKEN_STONE', os.environ.get('BOT_TOKEN', ''))
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID', '2114966435')
SELLER_CHAT_ID = os.environ.get('SELLER_CHAT_ID') or ADMIN_CHAT_ID
ADMIN_PASSWORD_STONE = os.environ.get('ADMIN_PASSWORD', '')
if not ADMIN_PASSWORD_STONE:
    print('[stone] WARNING: ADMIN_PASSWORD not set, admin panel disabled')

BASE_URL = os.environ.get('BASE_URL', 'https://torostore.ru')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '@storetoro')
TG_SELLER = os.environ.get('TG_SELLER', '@denayme')

PRODUCTS_PER_PAGE = int(os.environ.get('PRODUCTS_PER_PAGE', '50'))
ARCHIVE_PER_PAGE = int(os.environ.get('ARCHIVE_PER_PAGE', '200'))
VISIT_BATCH_SIZE = int(os.environ.get('VISIT_BATCH_SIZE', '20'))
STATS_CACHE_SECONDS = int(os.environ.get('STATS_CACHE_SECONDS', '15'))

IMAGE_QUALITY = int(os.environ.get('IMAGE_QUALITY', '92'))
IMAGE_THUMB_QUALITY = int(os.environ.get('IMAGE_THUMB_QUALITY', '85'))
