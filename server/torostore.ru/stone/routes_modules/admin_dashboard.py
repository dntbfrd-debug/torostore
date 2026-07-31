import json
import logging
from datetime import datetime
from flask import jsonify, request
from stone.models import StoneProduct, SupplyBatch, AdExpense
from models import db
from stone.utils import get_thumbnail
from stone.middleware import admin_required
from stone.routes import stone_bp

logger = logging.getLogger(__name__)


@stone_bp.route('/admin/api/dashboard')
@admin_required
def admin_api_dashboard():
    batches = SupplyBatch.query.order_by(SupplyBatch.created_at.desc()).all()
    batch_ids = [b.id for b in batches]

    # Bulk fetch ALL products for ALL batches in ONE query
    products_by_batch = {}
    if batch_ids:
        all_products = StoneProduct.query.filter(
            StoneProduct.supply_batch_id.in_(batch_ids)
        ).all()
        for p in all_products:
            products_by_batch.setdefault(p.supply_batch_id, []).append(p)

    result = []
    total_cost = 0
    total_revenue = 0
    total_projected = 0
    cost_sold = 0
    cost_unsold = 0
    projected_sold = 0
    projected_unsold = 0
    total_avito = 0
    total_cost_price = 0
    for b in batches:
        products = products_by_batch.get(b.id, [])
        sold_count = sum(1 for p in products if p.status == 'sold')
        total_count = len(products)
        actual_revenue = sum(p.sold_price or p.price for p in products if p.status == 'sold')
        projected_revenue = sum(p.price or 0 for p in products)
        products_cost = sum(p.cost_price or 0 for p in products)
        total_cost_price += products_cost
        products_repair = sum(p.repair_cost or 0 for p in products)
        products_avito = sum(p.avito_cost or 0 for p in products)

        # Sold vs unsold breakdown
        for p in products:
            p_full_cost = (p.cost_price or 0) + (p.repair_cost or 0) + (p.avito_cost or 0) + (b.delivery_cost / total_count if total_count else 0)
            p_price = p.price or 0
            if p.status == 'sold':
                cost_sold += p_full_cost
                projected_sold += p_price
            else:
                cost_unsold += p_full_cost
                projected_unsold += p_price

        total_avito += products_avito
        batch_total_cost = b.delivery_cost + products_cost + products_repair + products_avito
        total_cost += batch_total_cost
        total_revenue += actual_revenue
        total_projected += projected_revenue
        result.append({
            'id': b.id, 'name': b.name,
            'delivery_cost': b.delivery_cost,
            'products_cost': products_cost, 'products_repair': products_repair,
            'products_avito': products_avito,
            'total_cost': batch_total_cost,
            'total': total_count, 'sold': sold_count,
            'projected': projected_revenue,
            'revenue': actual_revenue, 'profit': actual_revenue - batch_total_cost,
            'created_at': b.created_at.strftime('%d.%m.%Y'),
        })

    expenses = AdExpense.query.order_by(AdExpense.created_at.desc()).all()
    global_ads = sum(e.amount for e in expenses)
    exp_list = [{
        'id': e.id,
        'amount': e.amount,
        'note': e.note or '',
        'date': e.created_at.strftime('%d.%m.%Y'),
    } for e in expenses]
    total_cost += global_ads

    # Aggregate orphan products without loading all rows
    from sqlalchemy import func, or_
    orphan_filter = or_(StoneProduct.supply_batch_id == None, StoneProduct.supply_batch_id == 0)
    orphan_revenue = db.session.query(func.coalesce(func.sum(StoneProduct.sold_price), 0)).filter(
        orphan_filter, StoneProduct.status == 'sold'
    ).scalar() or 0
    if orphan_revenue == 0:
        orphan_revenue = db.session.query(func.coalesce(func.sum(StoneProduct.price), 0)).filter(
            orphan_filter, StoneProduct.status == 'sold'
        ).scalar() or 0
    orphan_cost = db.session.query(func.coalesce(
        func.sum(func.coalesce(StoneProduct.cost_price, 0) + func.coalesce(StoneProduct.repair_cost, 0) + func.coalesce(StoneProduct.avito_cost, 0)), 0
    )).filter(orphan_filter, StoneProduct.status == 'sold').scalar() or 0
    orphan_projected = db.session.query(func.coalesce(func.sum(StoneProduct.price), 0)).filter(orphan_filter).scalar() or 0
    total_cost += orphan_cost
    total_revenue += orphan_revenue
    total_projected += orphan_projected
    cost_sold += orphan_cost
    projected_sold += orphan_revenue
    projected_unsold += (orphan_projected - orphan_revenue)

    return jsonify({
        'batches': result,
        'global_ads': global_ads,
        'expenses': exp_list,
        'total_cost': total_cost,
        'total_revenue': total_revenue,
        'total_projected': total_projected,
        'total_profit': total_revenue - total_cost,
        'cost_sold': int(cost_sold),
        'cost_unsold': int(cost_unsold),
        'projected_sold': int(projected_sold),
        'projected_unsold': int(projected_unsold),
        'markup_pct': int((total_projected / total_cost - 1) * 100) if total_cost else 0,
        'total_cost_price': int(total_cost_price),
    })


@stone_bp.route('/admin/api/batch', methods=['POST'])
@admin_required
def admin_api_batch_create():
    data = request.json or {}
    count = SupplyBatch.query.count()
    name = f"Поставка #{count + 1} от {datetime.utcnow().strftime('%d.%m.%y')}"
    b = SupplyBatch(
        name=name,
        delivery_cost=int(data.get('delivery_cost', 0)),
        notes=data.get('notes', '').strip()
    )
    db.session.add(b)
    db.session.commit()
    return jsonify({'success': True, 'id': b.id, 'name': b.name})


@stone_bp.route('/admin/api/batch/<int:batch_id>', methods=['DELETE'])
@admin_required
def admin_api_batch_delete(batch_id):
    b = SupplyBatch.query.get_or_404(batch_id)
    StoneProduct.query.filter_by(supply_batch_id=batch_id).update({'supply_batch_id': None})
    db.session.delete(b)
    db.session.commit()
    return jsonify({'success': True})


@stone_bp.route('/admin/api/batch/<int:batch_id>', methods=['POST'])
@admin_required
def admin_api_batch_update(batch_id):
    b = SupplyBatch.query.get_or_404(batch_id)
    data = request.json or {}
    if 'delivery_cost' in data:
        try:
            b.delivery_cost = int(data['delivery_cost']) or 0
        except Exception:
            pass
    db.session.commit()
    return jsonify({'success': True})


@stone_bp.route('/admin/api/batch/<int:batch_id>/link', methods=['POST'])
@admin_required
def admin_api_batch_link(batch_id):
    data = request.json or {}
    avito_ids = data.get('avito_ids', [])
    StoneProduct.query.filter(StoneProduct.avito_id.in_(avito_ids)).update(
        {'supply_batch_id': batch_id}, synchronize_session=False
    )
    db.session.commit()
    return jsonify({'success': True})


@stone_bp.route('/admin/api/batch/<int:batch_id>/products')
@admin_required
def admin_api_batch_products(batch_id):
    products = StoneProduct.query.filter_by(supply_batch_id=batch_id).order_by(StoneProduct.created_at.desc()).all()
    result = []
    for p in products:
        thumb = get_thumbnail(p)
        result.append({
            'avito_id': p.avito_id, 'title': p.title,
            'price': p.price, 'sold_price': p.sold_price or 0,
            'cost_price': p.cost_price or 0, 'repair_cost': p.repair_cost or 0,
            'avito_cost': p.avito_cost or 0, 'status': p.status or '',
            'is_active': p.is_active,
            'thumb': thumb,
        })
    return jsonify(result)


@stone_bp.route('/admin/api/ad-expense', methods=['POST'])
@admin_required
def admin_api_ad_expense_add():
    data = request.json or {}
    amount = int(data.get('amount', 0))
    if not amount:
        return jsonify({'error': 'Укажите сумму'}), 400
    note = data.get('note', '').strip()[:255]
    exp = AdExpense(amount=amount, note=note)
    db.session.add(exp)
    db.session.commit()
    return jsonify({'success': True, 'id': exp.id})


@stone_bp.route('/admin/api/ad-expense/<int:expense_id>', methods=['DELETE'])
@admin_required
def admin_api_ad_expense_delete(expense_id):
    exp = AdExpense.query.get_or_404(expense_id)
    db.session.delete(exp)
    db.session.commit()
    return jsonify({'success': True})
