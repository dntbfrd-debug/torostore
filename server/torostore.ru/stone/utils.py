import re
import logging

logger = logging.getLogger(__name__)

_SKIP_LINE_RE = re.compile(r'^[---]?\s*(размер|сезон|art|состояние|страна)')
_PRICE_RE = re.compile(r'Цена\s*[---]\s*\d[\d\s]*[?р]?\.?', re.IGNORECASE)
_NEWLINE_RE = re.compile(r'\n{3,}')


def extract_color(text):
    if not text:
        return ''
    for line in text.split('\n'):
        l = line.strip().lower()
        if l.startswith('- цвет') or l.startswith('цвет'):
            return line.split(':', 1)[-1].strip() if ':' in line else line.split('цвет', 1)[-1].strip().lstrip('.:- ')
    return ''


def _fix_img_url(url):
    if not url:
        return url
    url = url.replace('/stone/static/stone_imgs/', '/stone/media/')
    if url.endswith('.webp') and '/stone/media/' in url:
        url = url[:-5]
    return url


def normalize_description(desc, title):
    if not desc:
        return ''
    lines = desc.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(low.startswith(p) for p in ['- размер', 'размер:', '- сезон', 'сезон:', '- art', 'art:', '- состояние', 'состояние:', '- страна', 'страна:']):
            continue
        if _SKIP_LINE_RE.match(low):
            continue
        if title.lower() in low.replace('.', '').lower():
            continue
        clean.append(s)
    clean = [l for l in clean if l]
    result = '\n'.join(clean)
    result = _PRICE_RE.sub('', result)
    result = _NEWLINE_RE.sub('\n\n', result)
    return result.strip()

# ===== IMAGE HELPERS =====

def get_thumbnail(product):
    import json
    try:
        imgs = json.loads(product.images) if product.images else []
        return imgs[0] if imgs else ''
    except Exception:
        return ''


def attach_images_list(product):
    import json
    try:
        product.images_list = [_fix_img_url(u) for u in json.loads(product.images)] if product.images else []
    except Exception:
        product.images_list = []


def attach_images_to_products(products):
    for p in products:
        attach_images_list(p)
    return products
