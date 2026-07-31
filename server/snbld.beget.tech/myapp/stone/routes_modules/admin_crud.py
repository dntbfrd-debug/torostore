import json
import logging
from datetime import datetime, timedelta
from flask import jsonify, request
from stone.models import StoneProduct
from models import db
from stone.utils import _fix_img_url, normalize_description
from stone.config import PRODUCTS_PER_PAGE
from stone.middleware import admin_required
from stone.routes import stone_bp

logger = logging.getLogger(__name__)


@stone_bp.route('/admin/api/products')
@admin_required
def admin_api_products():
    products = StoneProduct.query.order_by(StoneProduct.created_at.desc()).limit(PRODUCTS_PER_PAGE).all()
    for p in products:
        try:
            p.images_list = [_fix_img_url(u) for u in json.loads(p.images)] if p.images else []
        except Exception:
            p.images_list = []
        p.clean_desc = normalize_description(p.description, p.title)
    return jsonify([p.to_dict() for p in products])


@stone_bp.route('/admin/api/archive', methods=['POST'])
@admin_required
def admin_api_archive():
    data = request.json
    avito_id = data.get('avito_id', '')
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    product.is_active = False
    product.status = 'sold'
    product.sold_at = datetime.utcnow()
    if 'supply_batch_id' in data and data['supply_batch_id']:
        product.supply_batch_id = int(data['supply_batch_id'])
    if 'sold_price' in data and data['sold_price']:
        product.sold_price = int(data['sold_price'])
    if not product.sold_price:
        product.sold_price = product.price
    db.session.commit()
    return jsonify({'success': True, 'avito_id': avito_id})


@stone_bp.route('/admin/api/reserve', methods=['POST'])
@admin_required
def admin_api_reserve():
    data = request.json
    avito_id = data.get('avito_id', '')
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    product.is_active = False
    product.status = 'reserved'
    db.session.commit()
    return jsonify({'success': True, 'avito_id': avito_id})


@stone_bp.route('/admin/api/delete', methods=['POST'])
@admin_required
def admin_api_delete():
    data = request.json
    avito_id = data.get('avito_id', '')
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    db.session.delete(product)
    db.session.commit()
    return jsonify({'success': True, 'avito_id': avito_id})


@stone_bp.route('/admin/api/restore', methods=['POST'])
@admin_required
def admin_api_restore():
    data = request.json
    avito_id = data.get('avito_id', '')
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    product.is_active = True
    product.status = ''
    product.sold_price = 0
    product.sold_at = None
    db.session.commit()
    return jsonify({'success': True, 'avito_id': avito_id})


@stone_bp.route('/admin/api/product/<avito_id>')
@admin_required
def admin_api_product(avito_id):
    p = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not p:
        return jsonify({'error': 'not found'}), 404
    try:
        p.images_list = [_fix_img_url(u) for u in json.loads(p.images)] if p.images else []
    except Exception:
        p.images_list = []
    return jsonify(p.to_dict())


@stone_bp.route('/admin/api/add', methods=['POST'])
@admin_required
def admin_api_add():
    data = request.json
    if not data:
        return jsonify({'error': 'no data'}), 400
    avito_id = data.get('avito_id', '').strip()
    if not avito_id:
        avito_id = 'st' + datetime.now().strftime('%y%m%d%H%M%S')
    existing = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if existing:
        return jsonify({'error': 'Товар с таким avito_id уже существует'}), 409
    try:
        images_list = data.get('images', [])
        if isinstance(images_list, str):
            images_list = [x.strip() for x in images_list.replace('\n', ',').split(',') if x.strip()]
        product = StoneProduct(
            avito_id=avito_id,
            title=data.get('title', '').strip(),
            description=data.get('description', '').strip(),
            price=int(data.get('price', 0)),
            price_string=f"{data.get('price', 0):,} ₽".replace(',', '.'),
            size=data.get('size', '').strip(),
            season=data.get('season', '').strip(),
            art=data.get('art', '').strip(),
            condition=data.get('condition', '').strip(),
            defects=data.get('defects', '').strip(),
            avito_url=data.get('avito_url', '').strip(),
            category=data.get('category', '').strip(),
            images=json.dumps(images_list, ensure_ascii=False),
            defect_images=json.dumps(data.get('defect_images', []), ensure_ascii=False),
            supply_batch_id=data.get('supply_batch_id') or None,
            cost_price=int(data.get('cost_price', 0)) or 0,
            avito_cost=int(data.get('avito_cost', 0)) or 0,
            repair_cost=int(data.get('repair_cost', 0)) or 0,
            sold_price=int(data.get('sold_price', 0)) or 0,
            old_price=int(data.get('old_price', 0)) or 0,
            is_active=True
        )
        discount_hours = int(data.get('discount_hours', 0)) or 0
        if discount_hours > 0:
            product.discount_ends_at = datetime.utcnow() + timedelta(hours=discount_hours)
        db.session.add(product)
        db.session.commit()
        return jsonify({'success': True, 'avito_id': avito_id, 'id': product.id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to add product: {e}")
        return jsonify({'error': str(e)}), 500


@stone_bp.route('/admin/api/update', methods=['POST'])
@admin_required
def admin_api_update():
    data = request.json
    if not data:
        return jsonify({'error': 'no data'}), 400
    avito_id = data.get('avito_id', '').strip()
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'Товар не найден'}), 404
    try:
        for field in ('title', 'description', 'size', 'season', 'art', 'condition', 'defects', 'avito_url', 'category'):
            val = data.get(field)
            if val is not None:
                setattr(product, field, str(val)[:1024].strip())
        if data.get('price') is not None:
            product.price = int(data['price'])
            product.price_string = f"{data['price']:,} ₽".replace(',', '.')
        if data.get('images') is not None:
            images_list = data['images']
            if isinstance(images_list, str):
                images_list = [x.strip() for x in images_list.replace('\n', ',').split(',') if x.strip()]
            product.images = json.dumps(images_list, ensure_ascii=False)
        if data.get('defect_images') is not None:
            product.defect_images = json.dumps(data['defect_images'], ensure_ascii=False)
        if 'supply_batch_id' in data:
            product.supply_batch_id = data['supply_batch_id'] or None
        if 'cost_price' in data:
            val = int(data['cost_price']) or 0
            if val > 0 or product.cost_price == 0:
                product.cost_price = val
        if 'avito_cost' in data:
            val = int(data['avito_cost']) or 0
            if val > 0 or product.avito_cost == 0:
                product.avito_cost = val
        if 'repair_cost' in data:
            val = int(data['repair_cost']) or 0
            if val > 0 or product.repair_cost == 0:
                product.repair_cost = val
        if 'sold_price' in data:
            product.sold_price = int(data['sold_price']) or 0
        if 'old_price' in data:
            product.old_price = int(data['old_price']) or 0
        if 'discount_hours' in data:
            hours = int(data['discount_hours']) or 0
            if hours > 0:
                product.discount_ends_at = datetime.utcnow() + timedelta(hours=hours)
            else:
                product.discount_ends_at = None
        db.session.commit()
        return jsonify({'success': True, 'avito_id': avito_id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to update product {avito_id}: {e}")
        return jsonify({'error': str(e)}), 500


@stone_bp.route('/admin/api/no-cost')
@admin_required
def admin_api_no_cost():
    products = StoneProduct.query.filter_by(is_active=True, cost_price=0).order_by(StoneProduct.created_at.desc()).all()
    result = []
    for p in products:
        thumb = ''
        try:
            imgs = json.loads(p.images) if p.images else []
            thumb = imgs[0] if imgs else ''
        except Exception:
            pass
        result.append({
            'avito_id': p.avito_id, 'title': p.title,
            'price': p.price, 'cost_price': p.cost_price or 0,
            'avito_cost': p.avito_cost or 0, 'repair_cost': p.repair_cost or 0,
            'thumb': thumb,
        })
    return jsonify(result)


@stone_bp.route('/admin/api/cost-bulk', methods=['POST'])
@admin_required
def admin_api_cost_bulk():
    data = request.json or {}
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'no items'}), 400
    updated = 0
    avito_ids = [item.get('avito_id', '') for item in items]
    prods = StoneProduct.query.filter(StoneProduct.avito_id.in_(avito_ids)).all()
    prod_by_id = {p.avito_id: p for p in prods}
    for item in items:
        avito_id = item.get('avito_id', '')
        p = prod_by_id.get(avito_id)
        if not p:
            continue
        if 'cost_price' in item:
            val = int(item['cost_price']) or 0
            if val > 0 or p.cost_price == 0:
                p.cost_price = val
        if 'avito_cost' in item:
            val = int(item['avito_cost']) or 0
            if val > 0 or p.avito_cost == 0:
                p.avito_cost = val
        if 'repair_cost' in item:
            val = int(item['repair_cost']) or 0
            if val > 0 or p.repair_cost == 0:
                p.repair_cost = val
        updated += 1
    db.session.commit()
    return jsonify({'success': True, 'updated': updated})
