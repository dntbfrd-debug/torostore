import requests
import json
import re
import sys
from datetime import datetime
from models import db
from stone.models import StoneProduct

AVITO_SELLER_ID = 'd18abebfaadf1239ac8806533322efb8'
AVITO_BRAND_ID = '56f71cdbc9862421c00323c8245a9725'
AVITO_API = 'https://www.avito.ru/web/1/profile/items'

def parse_attributes(description):
    size = ''
    season = ''
    art = ''
    condition = ''

    for line in description.split('\n'):
        line = line.strip()
        if line.lower().startswith('- размер') or line.lower().startswith('размер'):
            size = line.split(':', 1)[-1].strip() if ':' in line else line.split('размер', 1)[-1].strip().lstrip('.:- ')
        elif line.lower().startswith('- сезон') or line.lower().startswith('сезон'):
            season = line.split(':', 1)[-1].strip() if ':' in line else line.split('сезон', 1)[-1].strip().lstrip('.:- ')
        elif line.lower().startswith('- art') or line.lower().startswith('art'):
            art = line.split(':', 1)[-1].strip() if ':' in line else line.split('art', 1)[-1].strip().lstrip('.:- ')
        elif line.lower().startswith('- состояние') or line.lower().startswith('состояние'):
            condition = line.split(':', 1)[-1].strip() if ':' in line else line.split('состояние', 1)[-1].strip().lstrip('.:- ')

    return size, season, art, condition

def sync_from_avito():
    items = []
    offset = 0

    while True:
        params = {
            'sellerId': AVITO_SELLER_ID,
            'brandId': AVITO_BRAND_ID,
            'limit': 50,
            'offset': offset
        }
        try:
            resp = requests.get(AVITO_API, params=params, timeout=15,
                                headers={
                                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                                    'Accept': 'application/json, text/plain, */*',
                                    'Accept-Language': 'ru-RU,ru;q=0.9',
                                    'Referer': 'https://www.avito.ru/',
                                    'Origin': 'https://www.avito.ru',
                                })
            sys.stderr.write(f'[STONE SYNC] HTTP {resp.status_code} offset={offset}\n')
            data = resp.json()
        except Exception as e:
            sys.stderr.write(f'[STONE SYNC] API error: {e}\n')
            break

        catalog = data.get('catalog', {})
        batch = catalog.get('items', [])
        if not batch:
            sys.stderr.write(f'[STONE SYNC] No items in batch, keys={list(data.keys())}\n')
        items.extend(batch)

        total = data.get('totalCount', 0)
        found = data.get('foundCount', 0)
        if offset + len(batch) >= found or len(batch) == 0:
            break
        offset += len(batch)

    avito_ids = []
    for item in items:
        avito_id = str(item['id'])
        avito_ids.append(avito_id)
        title = item.get('title', '')
        description = item.get('description', '')
        price_info = item.get('priceDetailed', {})
        price = price_info.get('value', 0)
        price_string = price_info.get('fullString', '')
        url_path = item.get('urlPath', '')
        avito_url = f'https://www.avito.ru{url_path}' if url_path else ''

        size, season, art, condition = parse_attributes(description)

        images = []
        for img_set in item.get('images', []):
            img_url = img_set.get('636x636') or img_set.get('864x864') or img_set.get('472x472') or ''
            if img_url:
                images.append(img_url)

        existing = StoneProduct.query.filter_by(avito_id=avito_id).first()
        if existing:
            existing.title = title
            existing.description = description
            existing.price = price
            existing.price_string = price_string
            existing.images = json.dumps(images, ensure_ascii=False)
            existing.size = size
            existing.season = season
            existing.art = art
            existing.condition = condition
            existing.avito_url = avito_url
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
        else:
            product = StoneProduct(
                avito_id=avito_id,
                title=title,
                description=description,
                price=price,
                price_string=price_string,
                images=json.dumps(images, ensure_ascii=False),
                size=size,
                season=season,
                art=art,
                condition=condition,
                avito_url=avito_url,
                is_active=True
            )
            db.session.add(product)

    if avito_ids:
        StoneProduct.query.filter(~StoneProduct.avito_id.in_(avito_ids)).update(
            {'is_active': False}, synchronize_session=False
        )

    db.session.commit()
    return len(items)
