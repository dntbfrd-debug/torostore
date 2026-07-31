from datetime import datetime
import json
from models import db

CATEGORIES = {
    'jackets': 'Куртки',
    'hoodies': 'Худи/Зип худи',
    'sweaters': 'Свитера/свитшоты',
    'pants': 'Штаны/шорты',
    'accessories': 'Аксессуары',
}

class VisitorLog(db.Model):
    __tablename__ = 'visitor_log'
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(45), nullable=False, index=True)
    path = db.Column(db.String(256), default='')
    source = db.Column(db.String(16), default='site', index=True)
    device = db.Column(db.String(16), default='')
    browser = db.Column(db.String(32), default='')
    os = db.Column(db.String(32), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class SupplyBatch(db.Model):
    __tablename__ = 'supply_batch'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    delivery_cost = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AdExpense(db.Model):
    __tablename__ = 'ad_expense'
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Integer, default=0)
    note = db.Column(db.String(255), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class StoneProduct(db.Model):
    __tablename__ = 'stone_product'

    id = db.Column(db.Integer, primary_key=True)
    avito_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    price = db.Column(db.Integer, default=0, index=True)
    old_price = db.Column(db.Integer, default=0)
    discount_ends_at = db.Column(db.DateTime, nullable=True)
    price_string = db.Column(db.String(64), default='')
    images = db.Column(db.Text, default='[]')
    size = db.Column(db.String(32), default='')
    season = db.Column(db.String(128), default='')
    art = db.Column(db.String(64), default='')
    condition = db.Column(db.String(32), default='')
    defects = db.Column(db.String(512), default='')
    defect_images = db.Column(db.Text, default='[]')
    category = db.Column(db.String(32), default='', index=True)
    avito_url = db.Column(db.String(512), default='')
    is_active = db.Column(db.Boolean, default=True, index=True)
    status = db.Column(db.String(16), default='', index=True)
    views = db.Column(db.Integer, default=0)
    favs = db.Column(db.Integer, default=0)
    buys = db.Column(db.Integer, default=0)
    sold_price = db.Column(db.Integer, default=0)
    sold_at = db.Column(db.DateTime, nullable=True)
    cost_price = db.Column(db.Integer, default=0)
    avito_cost = db.Column(db.Integer, default=0)
    repair_cost = db.Column(db.Integer, default=0)
    supply_batch_id = db.Column(db.Integer, db.ForeignKey('supply_batch.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    def category_name(self):
        return CATEGORIES.get(self.category, '')

    def to_dict(self):
        try:
            imgs = json.loads(self.images) if self.images else []
        except Exception:
            imgs = []
        return {
            'id': self.id,
            'avito_id': self.avito_id,
            'title': self.title,
            'description': self.description,
            'clean_desc': getattr(self, 'clean_desc', self.description),
            'price': self.price,
            'old_price': self.old_price or 0,
            'discount_ends_at': self.discount_ends_at.isoformat() if self.discount_ends_at else None,
            'price_string': self.price_string,
            'images': imgs,
            'size': self.size,
            'season': self.season,
            'art': self.art,
            'condition': self.condition,
            'defects': self.defects,
            'defect_images': json.loads(self.defect_images) if self.defect_images else [],
            'category': self.category,
            'category_name': self.category_name(),
            'avito_url': self.avito_url,
            'is_active': self.is_active,
            'status': self.status or '',
            'views': self.views or 0,
            'favs': self.favs or 0,
            'buys': self.buys or 0,
            'sold_price': self.sold_price or 0,
            'sold_at': self.sold_at.strftime('%d.%m.%y') if self.sold_at else None,
            'cost_price': self.cost_price or 0,
            'avito_cost': self.avito_cost or 0,
            'repair_cost': self.repair_cost or 0,
            'supply_batch_id': self.supply_batch_id,
        }
