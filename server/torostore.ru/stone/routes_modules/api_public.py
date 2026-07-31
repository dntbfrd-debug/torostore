import re
from flask import jsonify, request
from stone.models import StoneProduct
from db import db
from stone.utils import normalize_description, _fix_img_url
from utils import rate_limit
from stone.config import PRODUCTS_PER_PAGE, ARCHIVE_PER_PAGE
from stone.routes import stone_bp
from sqlalchemy import case

_discount_first = case((StoneProduct.old_price > StoneProduct.price, 0), else_=1)

AVITO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')

def _valid_avito_id(avito_id):
    return bool(AVITO_ID_PATTERN.match(avito_id or ''))


@stone_bp.route('/api/products')
def api_products():
    products = StoneProduct.query.filter_by(is_active=True).order_by(_discount_first, StoneProduct.price.asc()).limit(PRODUCTS_PER_PAGE).all()
    for p in products:
        p.clean_desc = normalize_description(p.description, p.title)
    return jsonify([p.to_dict() for p in products])


@stone_bp.route('/api/archived')
def api_archived():
    products = StoneProduct.query.filter_by(is_active=False).order_by(StoneProduct.updated_at.desc()).limit(ARCHIVE_PER_PAGE).all()
    for p in products:
        p.clean_desc = normalize_description(p.description, p.title)
    return jsonify([p.to_dict() for p in products])


@stone_bp.route('/api/track/view/<avito_id>', methods=['POST'])
@rate_limit(max_per_minute=60)
def api_track_view(avito_id):
    if not _valid_avito_id(avito_id):
        return jsonify({'ok': True})
    p = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if p:
        p.views = (p.views or 0) + 1
        db.session.commit()
    return jsonify({'ok': True})


@stone_bp.route('/api/track/fav/<avito_id>', methods=['POST'])
@rate_limit(max_per_minute=60)
def api_track_fav(avito_id):
    if not _valid_avito_id(avito_id):
        return jsonify({'ok': True})
    data = request.json or {}
    p = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if p:
        if data.get('active'):
            p.favs = (p.favs or 0) + 1
        else:
            p.favs = max(0, (p.favs or 0) - 1)
        db.session.commit()
    return jsonify({'ok': True})


@stone_bp.route('/api/product/<int:product_id>')
def api_product(product_id):
    if product_id <= 0 or product_id > 999999:
        return jsonify({'error': 'invalid id'}), 400
    p = StoneProduct.query.get_or_404(product_id)
    return jsonify(p.to_dict())
