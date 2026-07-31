from flask import jsonify, request
from stone.models import StoneProduct
from models import db
from stone.utils import normalize_description, _fix_img_url
from utils import rate_limit
from stone.config import PRODUCTS_PER_PAGE, ARCHIVE_PER_PAGE
from stone.routes import stone_bp
from sqlalchemy import case

_discount_first = case((StoneProduct.old_price > StoneProduct.price, 0), else_=1)


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
def api_track_view(avito_id):
    p = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if p:
        p.views = (p.views or 0) + 1
        db.session.commit()
    return jsonify({'ok': True})


@stone_bp.route('/api/track/fav/<avito_id>', methods=['POST'])
def api_track_fav(avito_id):
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
    p = StoneProduct.query.get_or_404(product_id)
    return jsonify(p.to_dict())


