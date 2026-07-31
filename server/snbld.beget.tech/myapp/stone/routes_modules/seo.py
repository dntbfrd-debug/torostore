import time
import json
from stone.models import StoneProduct
from stone.config import BASE_URL
from stone.routes import stone_bp

_sitemap_cache = {'xml': None, 'ts': 0}
SITEMAP_CACHE_TTL = 3600  # 1 hour
SITEMAP_MAX_URLS = 1000


@stone_bp.route('/robots.txt')
@stone_bp.route('/robots')
def robots_txt():
    return (
        f"User-agent: *\n"
        f"Allow: /stone/\n"
        f"Disallow: /stone/admin/\n"
        f"Disallow: /stone/webapp\n"
        f"Disallow: /stone/api/\n"
        f"Sitemap: {BASE_URL}/stone/sitemap.xml\n",
        200,
        {'Content-Type': 'text/plain; charset=utf-8'},
    )


def invalidate_sitemap_cache():
    _sitemap_cache['xml'] = None
    _sitemap_cache['ts'] = 0


@stone_bp.route('/sitemap.xml')
def sitemap_xml():
    now = time.time()
    if _sitemap_cache['xml'] and (now - _sitemap_cache['ts']) < SITEMAP_CACHE_TTL:
        return _sitemap_cache['xml'], 200, {'Content-Type': 'application/xml; charset=utf-8'}

    products = StoneProduct.query.filter_by(is_active=True).order_by(
        StoneProduct.created_at.desc()
    ).limit(SITEMAP_MAX_URLS).all()

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
    xml += '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'

    xml += '  <url>\n'
    xml += f'    <loc>{BASE_URL}/stone/</loc>\n'
    xml += '    <changefreq>daily</changefreq>\n'
    xml += '    <priority>1.0</priority>\n'
    xml += '  </url>\n'

    for p in products:
        xml += '  <url>\n'
        xml += f'    <loc>{BASE_URL}/stone/p/{p.avito_id}</loc>\n'
        if p.updated_at:
            xml += f'    <lastmod>{p.updated_at.strftime("%Y-%m-%d")}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '    <priority>0.9</priority>\n'

        try:
            imgs = json.loads(p.images) if p.images else []
            for img in imgs[:5]:
                full_url = f'{BASE_URL}{img}' if img.startswith('/') else img
                xml += '    <image:image>\n'
                xml += f'      <image:loc>{full_url}</image:loc>\n'
                xml += f'      <image:title>{p.title}</image:title>\n'
                xml += '    </image:image>\n'
        except Exception:
            pass

        xml += '  </url>\n'

    xml += '</urlset>'

    _sitemap_cache['xml'] = xml
    _sitemap_cache['ts'] = now
    return xml, 200, {'Content-Type': 'application/xml; charset=utf-8'}
