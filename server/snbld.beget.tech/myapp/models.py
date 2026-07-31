# -*- coding: utf-8 -*-
"""
models.py
Модели базы данных для snbld resvap
ОБНОВЛЁННАЯ ВЕРСИЯ - без HWID, с сессиями
"""

from datetime import datetime, timedelta
import hashlib
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

TOKEN_EXPIRE_DAYS = 7


class User(db.Model):
    """Пользователь системы"""
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    hwid = db.Column(db.String(256), nullable=True)
    token = db.Column(db.String(256), unique=True, nullable=False)
    token_created = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), default='worker')
    telegram_id = db.Column(db.String(64), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    reg_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Активен')
    last_seen = db.Column(db.DateTime, nullable=True)

    keys = db.relationship('Key', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if '$' in (self.password_hash or ''):
            try:
                return check_password_hash(self.password_hash, password)
            except ValueError:
                pass
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    def needs_hash_upgrade(self):
        return bool(self.password_hash) and '$' not in self.password_hash

    def is_token_valid(self):
        if not self.token_created:
            return bool(self.token)
        return self.token_created > datetime.utcnow() - timedelta(days=TOKEN_EXPIRE_DAYS)


class UserToken(db.Model):
    """Токены для входа с разных устройств"""
    __tablename__ = 'user_token'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(256), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='tokens')

    def is_valid(self):
        return self.created_at > datetime.utcnow() - timedelta(days=TOKEN_EXPIRE_DAYS)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }

    def __repr__(self):
        return f'<UserToken user={self.user_id} ...{self.token[-8:] if self.token else ""}>'


class BannedHWID(db.Model):
    """Заблокированные HWID (для обратной совместимости)"""
    __tablename__ = 'banned_hwid'

    id = db.Column(db.Integer, primary_key=True)
    hwid = db.Column(db.String(256), unique=True, nullable=False)
    banned_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        """Преобразует в словарь"""
        return {
            'id': self.id,
            'hwid': self.hwid,
            'banned_at': self.banned_at.isoformat() if self.banned_at else None,
            'reason': self.reason
        }

    def __repr__(self):
        return f'<BannedHWID {self.hwid}>'


class Key(db.Model):
    """Ключи активации"""
    __tablename__ = 'key'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    key_type = db.Column(db.String(20), nullable=False)
    source = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    used_by = db.Column(db.String(256), nullable=True)  # ← Теперь хранит "activated" вместо HWID
    used_at = db.Column(db.DateTime, nullable=True)
    activated_at = db.Column(db.DateTime, nullable=True)  # ← Дата первой активации
    download_count = db.Column(db.Integer, default=0)  # ← Сколько раз скачан
    is_active = db.Column(db.Boolean, default=True)
    purchaser_tg_id = db.Column(db.String(64), nullable=True)
    purchaser_username = db.Column(db.String(128), nullable=True)

    # Связи
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    sessions = db.relationship('Session', backref='session_key', lazy='dynamic')

    @property
    def time_left(self):
        """Оставшееся время действия"""
        if not self.expires_at:
            return "бессрочно"
        delta = self.expires_at - datetime.utcnow()
        if delta.total_seconds() <= 0:
            return "истёк"
        days = delta.days
        hours = delta.seconds // 3600
        return f"{days}д {hours}ч"

    def is_valid(self):
        """Проверяет валидность ключа"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

    def to_dict(self):
        """Преобразует в словарь"""
        return {
            'id': self.id,
            'key': self.key,
            'key_type': self.key_type,
            'source': self.source,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_by': self.used_by,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'activated_at': self.activated_at.isoformat() if self.activated_at else None,
            'download_count': self.download_count,
            'is_active': self.is_active,
            'time_left': self.time_left
        }

    def __repr__(self):
        return f'<Key {self.key} ({self.key_type})>'


class Session(db.Model):
    """Сессии активации (НОВАЯ МОДЕЛЬ)"""
    __tablename__ = 'session'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    key_id = db.Column(db.Integer, db.ForeignKey('key.id'), nullable=False)
    key = db.Column(db.String(64), nullable=False)  # Дублирование для быстрого поиска
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def to_dict(self):
        """Преобразует в словарь"""
        return {
            'session_id': self.session_id,
            'key': self.key,
            'key_id': self.key_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_active': self.is_active
        }

    def __repr__(self):
        return f'<Session {self.session_id}>'


class Employee(db.Model):
    """Сотрудник для графика работ"""
    __tablename__ = 'employee'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True)
    avatar = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    shifts = db.relationship('ShiftEntry', backref='employee', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'is_active': self.is_active,
            'avatar': self.avatar,
        }

    def __repr__(self):
        return f'<Employee {self.name}>'


class ShiftEntry(db.Model):
    """Запись смены сотрудника"""
    __tablename__ = 'shift_entry'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    shift_type = db.Column(db.String(10), nullable=True)  # 'full', 'half', or None
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('employee_id', 'date', name='uq_employee_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'date': self.date.isoformat() if self.date else None,
            'shift_type': self.shift_type,
        }

    def __repr__(self):
        return f'<ShiftEntry emp={self.employee_id} date={self.date} type={self.shift_type}>'


class DailyRevenue(db.Model):
    """Выручка за день"""
    __tablename__ = 'daily_revenue'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    amount = db.Column(db.Float, default=0.0)
    entered_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_edited_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        editor_avatar = None
        editor_name = ''
        editor_id = self.last_edited_by or self.entered_by
        if editor_id and self.amount and self.amount > 0:
            u = User.query.get(editor_id)
            if u:
                editor_name = u.login
                emp = Employee.query.filter_by(user_id=editor_id).first()
                if emp and emp.avatar:
                    editor_avatar = '/static/avatars/' + emp.avatar
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'amount': self.amount,
            'creator_name': editor_name,
            'editor_avatar': editor_avatar,
            'editor_name': editor_name,
        }

    def __repr__(self):
        return f'<DailyRevenue date={self.date} amount={self.amount}>'


class DailyNote(db.Model):
    """Закуп / заметка на день"""
    __tablename__ = 'daily_notes'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    text = db.Column(db.Text, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    last_edited_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        editor_avatar = None
        editor_name = ''
        editor_id = self.last_edited_by or self.created_by
        if editor_id and (self.text or '').strip():
            u = User.query.get(editor_id)
            if u:
                editor_name = u.login
                emp = Employee.query.filter_by(user_id=editor_id).first()
                if emp and emp.avatar:
                    editor_avatar = '/static/avatars/' + emp.avatar
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'text': self.text or '',
            'creator_name': editor_name,
            'editor_avatar': editor_avatar,
            'editor_name': editor_name,
        }

    def __repr__(self):
        return f'<DailyNote date={self.date}>'


class ArrivalNote(db.Model):
    """Приход продукции за день"""
    __tablename__ = 'arrival_notes'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    text = db.Column(db.Text, default='')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    photos = db.relationship('ArrivalPhoto', backref='arrival', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        creator_name = ''
        if self.created_by:
            u = User.query.get(self.created_by)
            if u:
                creator_name = u.login
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'text': self.text or '',
            'created_by': self.created_by,
            'creator_name': creator_name,
            'photo_count': self.photos.count(),
            'photos': [p.filename for p in self.photos.order_by(ArrivalPhoto.id).all()],
        }

    def __repr__(self):
        return f'<ArrivalNote date={self.date}>'


class ArrivalPhoto(db.Model):
    """Фото прихода"""
    __tablename__ = 'arrival_photos'

    id = db.Column(db.Integer, primary_key=True)
    arrival_id = db.Column(db.Integer, db.ForeignKey('arrival_notes.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SpecialDay(db.Model):
    """Особые дни: праздники, больничные, отпуска"""
    __tablename__ = 'special_days'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    day_type = db.Column(db.String(20), nullable=False)  # 'holiday','sick','vacation'
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('date', 'employee_id', name='uq_special_day'),)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'day_type': self.day_type,
            'employee_id': self.employee_id,
        }


class ChatMessage(db.Model):
    """Чат дашборда — сообщения живут 12 часов"""
    __tablename__ = 'chat_message'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    employee = db.relationship('Employee', backref='chat_messages')

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.name if self.employee else '?',
            'avatar': self.employee.avatar if self.employee else None,
            'text': self.text,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


class StoneChatMessage(db.Model):
    """Чат Stone Store"""
    __tablename__ = 'stone_chat'

    id = db.Column(db.Integer, primary_key=True)
    avito_id = db.Column(db.String(32), nullable=False, index=True)
    session_token = db.Column(db.String(32), default='')
    user_name = db.Column(db.String(128), default='Гость')
    user_contact = db.Column(db.String(128), default='')
    message = db.Column(db.Text, nullable=False)
    is_owner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_chat_avito_created', 'avito_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'avito_id': self.avito_id,
            'user_name': self.user_name,
            'user_contact': self.user_contact,
            'message': self.message,
            'is_owner': self.is_owner,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }


def init_db(app):
    """Инициализирует базу данных"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # Миграция: добавляем колонки если их нет
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [c['name'] for c in inspector.get_columns('user')]
            if 'role' not in columns:
                db.session.execute(db.text('ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT "worker"'))
                db.session.commit()
            if 'token_created' not in columns:
                db.session.execute(db.text('ALTER TABLE user ADD COLUMN token_created DATETIME'))
                db.session.commit()
        except Exception:
            pass
        
        # Миграция: old_price для StoneProduct (скидочная цена)
        try:
            from sqlalchemy import inspect as _inspect2
            _insp2 = _inspect2(db.engine)
            sp_cols = [c['name'] for c in _insp2.get_columns('stone_product')]
            if 'old_price' not in sp_cols:
                db.session.execute(db.text('ALTER TABLE stone_product ADD COLUMN old_price INTEGER DEFAULT 0'))
                db.session.commit()
            if 'discount_ends_at' not in sp_cols:
                db.session.execute(db.text('ALTER TABLE stone_product ADD COLUMN discount_ends_at DATETIME'))
                db.session.commit()
        except Exception:
            pass
        
        # Создаём индексы для дашборда (если их нет)
        try:
            db.session.execute(db.text('CREATE INDEX IF NOT EXISTS idx_shift_entry_date ON shift_entry(date)'))
            db.session.execute(db.text('CREATE INDEX IF NOT EXISTS idx_chat_message_created ON chat_message(created_at)'))
            db.session.execute(db.text('CREATE INDEX IF NOT EXISTS idx_arrival_photos_filename ON arrival_photos(filename)'))
            db.session.execute(db.text('CREATE INDEX IF NOT EXISTS idx_arrival_photos_aid ON arrival_photos(arrival_id)'))
            db.session.execute(db.text('CREATE INDEX IF NOT EXISTS idx_employee_name ON employee(name)'))
            db.session.commit()
        except Exception:
            pass

        # Создаём админа по умолчанию, если нет ни одного админа
        try:
            from sqlalchemy import text
            admin_exists = db.session.execute(text("SELECT COUNT(*) FROM user WHERE role = 'admin'")).scalar()
            if not admin_exists:
                # Создаём админа с логином из ADMIN_PASSWORD или 'admin'
                import os
                admin_login = os.environ.get('ADMIN_LOGIN', 'admin')
                admin_pwd = os.environ.get('ADMIN_PASSWORD', 'admin123')
                import secrets
                import hashlib
                existing = db.session.execute(text("SELECT id FROM user WHERE login = :l"), {'l': admin_login}).first()
                if not existing:
                    token = secrets.token_urlsafe(32)
                    hwid = 'web_admin_' + secrets.token_hex(8)
                    password_hash = hashlib.sha256(admin_pwd.encode()).hexdigest()
                    db.session.execute(text(
                        "INSERT INTO user (login, password_hash, token, hwid, role, status, reg_date) "
                        "VALUES (:l, :p, :t, :h, 'admin', 'Активен', :n)"
                    ), {'l': admin_login, 'p': password_hash, 't': token, 'h': hwid, 'n': datetime.utcnow()})
                    db.session.commit()
        except Exception:
            pass


class SystemFlag(db.Model):
    __tablename__ = 'system_flag'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value = db.Column(db.String(256), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RevisionNote(db.Model):
    """Лист ревизии — структурированный список товаров"""
    __tablename__ = 'revision_notes'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    text = db.Column(db.Text, default='')
    items_json = db.Column(db.Text, default='[]')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        creator_name = ''
        if self.created_by:
            u = User.query.get(self.created_by)
            if u:
                creator_name = u.login
        import json as _json
        try:
            items = _json.loads(self.items_json) if self.items_json else []
        except Exception:
            items = []
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'text': self.text or '',
            'items': items,
            'created_by': self.created_by,
            'creator_name': creator_name,
        }

    def __repr__(self):
        return f'<RevisionNote date={self.date}>'
