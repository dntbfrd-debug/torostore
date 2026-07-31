from flask import Flask, request, send_file, session as fsession
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import uuid
import requests
from flask_cors import CORS

from config import (PLATEGA_MERCHANT_ID, PLATEGA_SECRET, PLATEGA_API_URL,
                    BOT_TOKEN, ADMIN_CHAT_ID, GROUP_CHAT_ID, DOWNLOAD_URL,
                    SCHEDULE_CHAT_ID, VK_API_TOKEN, VK_USER_ID)
from models import (User, BannedHWID, Key, Session, Employee, ShiftEntry,
                    DailyRevenue, DailyNote, ArrivalNote, ArrivalPhoto,
                    SpecialDay, ChatMessage, UserToken, init_db, db)


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

CORS(app, origins=['https://snbld.ru', 'https://snbld.beget.tech', 'https://torrostore.ru'])

# ===== Конфигурация сессий =====
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    import secrets as _secrets
    app.config['SECRET_KEY'] = _secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "users.db")}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


init_db(app)


# ===== Настройки Telegram =====

BOT_TOKEN = BOT_TOKEN
ADMIN_CHAT_ID = ADMIN_CHAT_ID
GROUP_CHAT_ID = GROUP_CHAT_ID
SCHEDULE_CHAT_ID = SCHEDULE_CHAT_ID
DOWNLOAD_URL = DOWNLOAD_URL if DOWNLOAD_URL else "https://snbld.ru/webapp"

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), 'downloads')


def _verify_platega_signature(data: dict, signature: str) -> bool:
    if not signature:
        return False
    payload = json.dumps(data, sort_keys=True)
    expected = hmac.new(
        PLATEGA_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def _find_latest_zip():
    if not os.path.exists(DOWNLOADS_DIR):
        return None
    pattern = re.compile(r'^snbld_resvap_\d+\.\d+\.\d+\.zip$')
    files = [f for f in os.listdir(DOWNLOADS_DIR) if pattern.match(f)]
    if not files:
        return None
    return sorted(files)[-1]


def cleanup_expired_key(key):
    Session.query.filter_by(key_id=key.id).delete()
    db.session.delete(key)
    db.session.commit()


def verify_telegram_webhook():
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    expected = os.environ.get('TG_WEBHOOK_SECRET', '')
    if not expected or not secret:
        return False
    return hmac.compare_digest(secret, expected)

# =============================


# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------


def generate_token():

    return secrets.token_urlsafe(32)



def generate_fsession_id():

    return secrets.token_hex(32)



def is_hwid_banned(hwid):

    if not hwid:

        return False

    return BannedHWID.query.filter_by(hwid=hwid).first() is not None



def send_telegram_message(chat_id, text):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:

        requests.post(url, data=data, timeout=5)

    except Exception as e:

        sys.stderr.write(f"Ошибка отправки в Telegram: {e}\n")



def send_vk_message(user_id, text, attachment=None):
    import random
    if isinstance(user_id, str) and ',' in user_id:
        ids = [x.strip() for x in user_id.split(',')]
    elif isinstance(user_id, (list, tuple)):
        ids = list(user_id)
    else:
        ids = [user_id]
    results = []
    for uid in ids:
        url = "https://api.vk.com/method/messages.send"
        data = {
            "user_id": uid,
            "message": text,
            "random_id": random.randint(0, 2147483647),
            "access_token": VK_API_TOKEN,
            "v": "5.199"
        }
        if attachment:
            data["attachment"] = attachment
        try:
            r = requests.post(url, data=data, timeout=10)
            result = r.json()
            if "error" in result:
                sys.stderr.write(f"VK API error (uid={uid}): {result['error']}\n")
                results.append(None)
            else:
                results.append(result)
        except Exception as e:
            sys.stderr.write(f"VK send error (uid={uid}): {e}\n")
            results.append(None)
    return results[0] if results else None


def upload_vk_photo(filepath):
    url = "https://api.vk.com/method/photos.getMessagesUploadServer"
    try:
        r = requests.post(url, data={"access_token": VK_API_TOKEN, "v": "5.199"}, timeout=10)
        upload_data = r.json()
    except Exception as e:
        sys.stderr.write(f"VK getUploadServer error: {e}\n")
        return None

    if "error" in upload_data:
        sys.stderr.write(f"VK getUploadServer error: {upload_data['error']}\n")
        return None

    upload_url = upload_data["response"]["upload_url"]

    try:
        with open(filepath, "rb") as f:
            r = requests.post(upload_url, files={"photo": (os.path.basename(filepath), f)}, timeout=30)
        photo_data = r.json()
    except Exception as e:
        sys.stderr.write(f"VK upload photo error: {e}\n")
        return None

    if "error" in photo_data:
        sys.stderr.write(f"VK upload photo error: {photo_data['error']}\n")
        return None

    save_url = "https://api.vk.com/method/photos.saveMessagesPhoto"
    save_params = {
        "access_token": VK_API_TOKEN,
        "v": "5.199",
        "photo": photo_data["photo"],
        "server": photo_data["server"],
        "hash": photo_data["hash"]
    }
    try:
        r = requests.post(save_url, data=save_params, timeout=10)
        save_result = r.json()
    except Exception as e:
        sys.stderr.write(f"VK savePhoto error: {e}\n")
        return None

    if "error" in save_result:
        sys.stderr.write(f"VK savePhoto error: {save_result['error']}\n")
        return None

    photo = save_result["response"][0]
    return f"photo{photo['owner_id']}_{photo['id']}"



def generate_key(key_type, source='tribute'):
    return str(uuid.uuid4()).replace('-', '')[:16].upper()


def get_key_type_by_price(price_kopecks):

    mapping = {
        70000: '30d',
        370000: '180d',
        770000: '365d',
        1000000: 'permanent'
    }

    return mapping.get(price_kopecks)



def get_key_type_by_name(name):

    mapping = {

        'ну затестить чисто': '30d',

        'работяга': '180d',

        'ПАПА': '365d',

        'че?реально?': 'permanent'

    }

    return mapping.get(name)



def get_expiry_date(key_type):

    if key_type == 'test':

        return datetime.utcnow() + timedelta(days=1)

    elif key_type == '2m':
        return datetime.utcnow() + timedelta(minutes=2)

    elif key_type == '30d':

        return datetime.utcnow() + timedelta(days=30)

    elif key_type == '180d':

        return datetime.utcnow() + timedelta(days=180)

    elif key_type == '365d':

        return datetime.utcnow() + timedelta(days=365)

    else:

        return None



def get_active_key_for_hwid(hwid):

    if not hwid:

        return None

    return Key.query.filter_by(used_by=hwid, is_active=True).first()



def check_key_validity_for_hwid(hwid):

    key = get_active_key_for_hwid(hwid)

    if not key:

        return False

    if key.expires_at and key.expires_at < datetime.utcnow():
        # Удаляем связанные сессии
        fsessions = Session.query.filter_by(key_id=key.id).all()
        for s in fsessions:
            db.session.delete(s)
        # Удаляем ключ
        db.session.delete(key)
        db.session.commit()
        return False

    return True


def generate_invite_link():

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"

    data = {"chat_id": GROUP_CHAT_ID, "member_limit": 1, "expire_date": None}

    try:

        response = requests.post(url, json=data, timeout=10)

        result = response.json()

        if result.get("ok"):

            return result["result"]["invite_link"]

        else:

            sys.stderr.write(f"Ошибка создания ссылки: {result}\n")

            return None

    except Exception as e:

        sys.stderr.write(f"Ошибка при создании ссылки: {e}\n")

        return None


# =============================
# РЕГИСТРАЦИЯ BLUEPRINTS
# =============================

from routes.admin import admin_bp
from routes.auth import auth_bp
from routes.webapp import webapp_bp
from routes.dashboard import dashboard_bp
from routes.static_routes import static_bp
from routes.keys import keys_bp
from routes.payment import payment_bp
from routes.telegram import telegram_bp
from stone.routes import stone_bp

app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(webapp_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(static_bp)
app.register_blueprint(keys_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(telegram_bp)
app.register_blueprint(stone_bp)


# ===== Ежедневное напоминание в 21:00 =====
def daily_reminder():
    import time as _time
    while True:
        now = datetime.now()
        target = now.replace(hour=21, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        _time.sleep(wait)
        try:
            with app.app_context():
                today = datetime.now().date()
                shifts = ShiftEntry.query.filter(ShiftEntry.date == today, ShiftEntry.shift_type == 'full').all()
                if shifts:
                    names = []
                    for s in shifts:
                        emp = Employee.query.get(s.employee_id)
                        if emp:
                            names.append(emp.name)
                    if names:
                        from models import SystemFlag
                        flag = SystemFlag.query.filter_by(key=f'reminder_{today.isoformat()}').first()
                        if not flag:
                            db.session.add(SystemFlag(key=f'reminder_{today.isoformat()}', value='sent'))
                            db.session.commit()
                            msg = '🔔 ' + ', '.join(names) + ' — сегодня на смене!\nНе забудьте указать выручку и закуп в дашборде'
                            send_telegram_message(SCHEDULE_CHAT_ID, msg)
                expired_keys = Key.query.filter(
                    Key.expires_at != None,
                    Key.expires_at < datetime.utcnow()
                ).all()
                for key in expired_keys:
                    Session.query.filter_by(key_id=key.id).delete()
                    db.session.delete(key)
                if expired_keys:
                    db.session.commit()
                db.session.remove()
        except Exception as e:
            sys.stderr.write(f"[REMINDER ERROR] {e}\n")

reminder_thread = threading.Thread(target=daily_reminder, daemon=True)
reminder_thread.start()


# ===== Ежедневный бэкап users.db в 04:00 =====
def daily_backup():
    import time as _time
    import shutil
    import glob as _glob
    while True:
        now = datetime.now()
        target = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait = (target - now).total_seconds()
        _time.sleep(wait)
        try:
            bak_dir = os.path.join(basedir, 'backups')
            os.makedirs(bak_dir, exist_ok=True)
            db_path = os.path.join(basedir, 'users.db')
            stamp = datetime.now().strftime('%Y%m%d')
            bak_path = os.path.join(bak_dir, f'users_{stamp}.db')
            shutil.copy2(db_path, bak_path)
            sys.stderr.write(f"[BACKUP] Saved {bak_path}\n")
            # Ротация: храним только последние 30 копий
            all_baks = sorted(_glob.glob(os.path.join(bak_dir, 'users_*.db')))
            while len(all_baks) > 30:
                old = all_baks.pop(0)
                os.remove(old)
                sys.stderr.write(f"[BACKUP] Removed old {old}\n")
        except Exception as e:
            sys.stderr.write(f"[BACKUP ERROR] {e}\n")

backup_thread = threading.Thread(target=daily_backup, daemon=True)
backup_thread.start()


@app.after_request
def add_no_cache(response):
    if request.path.startswith('/dashboard'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


if __name__ == '__main__':
    app.run()
