import logging
from flask import render_template, session, make_response
from stone.models import StoneProduct
from stone.utils import normalize_description, extract_color, attach_images_to_products
from stone.config import PRODUCTS_PER_PAGE, ARCHIVE_PER_PAGE
from stone.routes import stone_bp
from datetime import datetime
from sqlalchemy import case

logger = logging.getLogger(__name__)

_discount_first = case((StoneProduct.old_price > StoneProduct.price, 0), else_=1)


def _fetch_active_products():
    products = StoneProduct.query.filter_by(is_active=True).order_by(
        _discount_first, StoneProduct.created_at.desc()
    ).limit(PRODUCTS_PER_PAGE).all()
    attach_images_to_products(products)
    for p in products:
        p.color = extract_color(p.description or '')
    return products


@stone_bp.route('/')
def catalog():
    products = _fetch_active_products()
    is_admin = session.get('stone_admin_logged_in', False)
    resp = make_response(render_template('stone_catalog.html', products=products, is_admin=is_admin, now=datetime.utcnow()))
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp


@stone_bp.route('/archive')
def archive_page():
    products = StoneProduct.query.filter_by(is_active=False).order_by(StoneProduct.updated_at.desc()).limit(ARCHIVE_PER_PAGE).all()
    attach_images_to_products(products)
    for p in products:
        p.color = extract_color(p.description or '')
    is_admin = session.get('stone_admin_logged_in', False)
    resp = make_response(render_template('stone_archive.html', products=products, is_admin=is_admin))
    resp.headers['X-Robots-Tag'] = 'noindex'
    return resp


@stone_bp.route('/webapp')
def webapp():
    session['stone_is_webapp'] = True
    products = _fetch_active_products()
    is_admin = session.get('stone_admin_logged_in', False)
    resp = make_response(render_template('stone_catalog.html', products=products, is_admin=is_admin, is_webapp=True, now=datetime.utcnow()))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@stone_bp.route('/p/<avito_id>')
def product_page(avito_id):
    from flask import redirect, url_for
    p = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not p:
        return redirect(url_for('stone.catalog'))
    products = _fetch_active_products()
    for prod in products:
        prod.clean_desc = normalize_description(prod.description, prod.title)
    resp = make_response(render_template('stone_catalog.html', products=products, is_admin=session.get('stone_admin_logged_in', False), auto_open_avito=avito_id, now=datetime.utcnow()))
    resp.headers['Cache-Control'] = 'public, max-age=300'
    return resp
