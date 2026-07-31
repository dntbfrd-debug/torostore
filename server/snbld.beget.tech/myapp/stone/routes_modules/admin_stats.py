import logging
import json
from flask import jsonify
from models import db, StoneChatMessage
from stone.models import StoneProduct, VisitorLog, AdExpense, SupplyBatch, CATEGORIES
from stone.config import STATS_CACHE_SECONDS
from stone.middleware import admin_required, _visit_batch, _visit_counter
from stone.routes import stone_bp
from datetime import datetime, timedelta
from sqlalchemy import func as _func

logger = logging.getLogger(__name__)

_stats_cache = {'data': None, 'ts': None}


def _query_value(q):
    try:
        return q.scalar() or 0
    except Exception:
        return 0


@stone_bp.route('/admin/api/stats')
@admin_required
def admin_stats():
    now = datetime.utcnow()
    if _visit_batch:
        try:
            db.session.add_all(_visit_batch)
            db.session.commit()
        except Exception:
            db.session.rollback()
        _visit_batch.clear()
        _visit_counter = 0

    if _stats_cache['data'] and _stats_cache['ts'] and (now - _stats_cache['ts']).seconds < STATS_CACHE_SECONDS:
        return jsonify(_stats_cache['data'])

    # --- Visitors helpers ---
    def count_ips(source, since, until=None):
        q = db.session.query(_func.count(_func.distinct(VisitorLog.ip))).filter(
            VisitorLog.source == source, VisitorLog.created_at >= since
        )
        if until:
            q = q.filter(VisitorLog.created_at < until)
        return _query_value(q)

    def count_views(source, since, until=None):
        q = VisitorLog.query.filter_by(source=source).filter(
            VisitorLog.created_at >= since
        )
        if until:
            q = q.filter(VisitorLog.created_at < until)
        return q.count() or 0

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # --- Daily trend (last 7 days) ---
    daily = []
    for d in range(6, -1, -1):
        ds = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=d)
        de = ds + timedelta(days=1)
        daily.append({
            'date': ds.strftime('%d.%m'),
            'site_ips': count_ips('site', ds, de) if ds != today_start else count_ips('site', today_start),
            'wa_ips': count_ips('webapp', ds, de) if ds != today_start else count_ips('webapp', today_start),
        })

    # --- Weekly sales trend (last 4 weeks) ---
    weekly = []
    prev_monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    for w in range(3, -1, -1):
        ws = prev_monday - timedelta(days=7 * w)
        we = ws + timedelta(days=7)
        sold_in_week = StoneProduct.query.filter(
            StoneProduct.status == 'sold', StoneProduct.sold_at >= ws, StoneProduct.sold_at < we
        ).count()
        revenue_in_week = _query_value(
            db.session.query(_func.sum(_func.coalesce(StoneProduct.sold_price, StoneProduct.price))).filter(
                StoneProduct.status == 'sold', StoneProduct.sold_at >= ws, StoneProduct.sold_at < we
            )
        )
        weekly.append({
            'week': ws.strftime('%d.%m'),
            'sold_count': sold_in_week,
            'revenue': revenue_in_week,
        })

    # --- Product & engagement ---
    active_prods = StoneProduct.query.filter_by(is_active=True).count()
    sold_count = StoneProduct.query.filter_by(is_active=False, status='sold').count()
    reserved_count = StoneProduct.query.filter_by(is_active=False, status='reserved').count()
    total_views = _query_value(db.session.query(_func.sum(StoneProduct.views)))
    total_favs = _query_value(db.session.query(_func.sum(StoneProduct.favs)))
    purchases = StoneChatMessage.query.filter_by(is_owner=False).distinct(StoneChatMessage.avito_id).count()
    conversion_rate = round(purchases / total_views * 100, 1) if total_views else 0

    # --- Top products ---
    top_products_db = StoneProduct.query.filter_by(is_active=True).order_by(
        StoneProduct.views.desc()
    ).limit(5).all()
    top_products = []
    for p in top_products_db:
        thumb = ''
        try:
            imgs = json.loads(p.images) if p.images else []
            thumb = imgs[0] if imgs else ''
        except Exception:
            pass
        top_products.append({
            'avito_id': p.avito_id, 'title': p.title, 'views': p.views or 0,
            'favs': p.favs or 0, 'price': p.price, 'thumb': thumb,
        })

    # --- Top sold ---
    top_sold_db = StoneProduct.query.filter_by(status='sold').order_by(
        StoneProduct.sold_at.desc()
    ).limit(5).all()
    top_sold = []
    for p in top_sold_db:
        thumb = ''
        try:
            imgs = json.loads(p.images) if p.images else []
            thumb = imgs[0] if imgs else ''
        except Exception:
            pass
        top_sold.append({
            'avito_id': p.avito_id, 'title': p.title,
            'sold_price': p.sold_price or p.price,
            'sold_at': p.sold_at.strftime('%d.%m.%y') if p.sold_at else '',
            'thumb': thumb,
        })

    # --- Categories ---
    cats = db.session.query(StoneProduct.category, _func.count(StoneProduct.id)).filter(
        StoneProduct.is_active == True, StoneProduct.category != ''
    ).group_by(StoneProduct.category).all()
    categories = [{'name': CATEGORIES.get(c, '?'), 'count': n} for c, n in cats]

    # --- Sizes ---
    size_order = ['XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL']
    sizes_raw = {}
    active_all = StoneProduct.query.filter_by(is_active=True).all()
    for p in active_all:
        if p.size:
            for token in p.size.upper().replace('(', '').replace(')', '').replace('/', ',').split(','):
                token = token.strip()
                if token:
                    sizes_raw[token] = sizes_raw.get(token, 0) + 1
    sizes = [{'size': k, 'count': v} for k, v in sorted(
        sizes_raw.items(),
        key=lambda x: (size_order.index(x[0]) if x[0] in size_order else 999, x[0])
    )]

    # --- Device analytics (last 30 days) ---
    month_ago = now - timedelta(days=30)
    device_q = db.session.query(
        VisitorLog.device, _func.count(_func.distinct(VisitorLog.ip))
    ).filter(
        VisitorLog.created_at >= month_ago, VisitorLog.device != ''
    ).group_by(VisitorLog.device).all()
    devices = [{'name': d or 'other', 'count': c} for d, c in device_q]

    browser_q = db.session.query(
        VisitorLog.browser, _func.count(_func.distinct(VisitorLog.ip))
    ).filter(
        VisitorLog.created_at >= month_ago, VisitorLog.browser != ''
    ).group_by(VisitorLog.browser).all()
    browsers = [{'name': b or 'other', 'count': c} for b, c in browser_q]

    os_q = db.session.query(
        VisitorLog.os, _func.count(_func.distinct(VisitorLog.ip))
    ).filter(
        VisitorLog.created_at >= month_ago, VisitorLog.os != ''
    ).group_by(VisitorLog.os).all()
    oses = [{'name': o or 'other', 'count': c} for o, c in os_q]

    # --- Today visitors ---
    site_today_ips = count_ips('site', today_start)
    wa_today_ips = count_ips('webapp', today_start)
    site_today_hits = count_views('site', today_start)
    wa_today_hits = count_views('webapp', today_start)

    # --- Online right now (last 5 min) ---
    five_min_ago = now - timedelta(minutes=5)
    online_now = _query_value(
        db.session.query(_func.count(_func.distinct(VisitorLog.ip))).filter(
            VisitorLog.created_at >= five_min_ago
        )
    )

    result = {
        'overview': {'active': active_prods, 'sold': sold_count, 'reserved': reserved_count},
        'engagement': {
            'total_views': total_views, 'total_favs': total_favs,
            'purchases': purchases, 'conversion_rate': conversion_rate,
        },
        'visitors': {
            'site_today_ips': site_today_ips, 'webapp_today_ips': wa_today_ips,
            'site_today_hits': site_today_hits, 'webapp_today_hits': wa_today_hits,
            'online_now': online_now,
        },
        'daily': daily,
        'weekly': weekly,
        'top_products': top_products,
        'top_sold': top_sold,
        'categories': categories,
        'sizes': sizes,
        'devices': devices,
        'browsers': browsers,
        'oses': oses,
    }
    _stats_cache['data'] = result
    _stats_cache['ts'] = now
    return jsonify(result)
