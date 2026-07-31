import logging
import re
import time
from functools import wraps
from flask import request, jsonify, session, redirect, url_for
from models import db
from stone.models import VisitorLog
from stone.config import ADMIN_PASSWORD_STONE, VISIT_BATCH_SIZE

logger = logging.getLogger(__name__)

_visit_batch = []
_visit_counter = 0
_visit_ip_times = {}  # {ip: last_logged_timestamp}
VISIT_IP_COOLDOWN = 5  # seconds between visits from same IP

_BOT_PATTERNS = re.compile(
    r'bot|crawl|spider|scrap|curl|wget|python|java|http|scan|'
    r'checker|monitor|uptime|yandex|googlebot|bingbot|slurp|'
    r'duckduck|baidu|facebook|twitter|linkedin|whatsapp|'
    r'telegrambot|vk|ahrefs|semrush|majestic|rogerbot|'
    r'dotbot|pinterest|applebot|petal|sogou|yisou',
    re.IGNORECASE,
)

_BOT_IPS = {'127.0.0.1', '::1', '0.0.0.0'}


def _is_bot():
    ua = request.headers.get('User-Agent', '')
    if not ua or len(ua) < 20:
        return True
    if _BOT_PATTERNS.search(ua):
        return True
    ip = request.remote_addr or ''
    if ip in _BOT_IPS:
        return True
    if ip.startswith(('10.', '192.168.', '172.16.', '172.17.', '172.18.',
                      '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
                      '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
                      '172.29.', '172.30.', '172.31.')):
        return True
    return False


def _parse_ua(ua):
    dev = 'desktop'
    br = 'other'
    os = 'other'
    if not ua:
        return dev, br, os
    low = ua.lower()
    if 'mobile' in low or 'android' in low and 'tablet' not in low:
        dev = 'phone'
    elif 'tablet' in low or 'ipad' in low:
        dev = 'tablet'
    if 'iphone' in low or 'ipad' in low or 'ipod' in low:
        os = 'iOS'
    elif 'android' in low:
        os = 'Android'
    elif 'windows' in low:
        os = 'Windows'
    elif 'macintosh' in low or 'mac os' in low:
        os = 'macOS'
    elif 'linux' in low:
        os = 'Linux'
    if 'chrome' in low and 'edg' not in low:
        br = 'Chrome'
    elif 'firefox' in low:
        br = 'Firefox'
    elif 'safari' in low and 'chrome' not in low:
        br = 'Safari'
    elif 'edg' in low:
        br = 'Edge'
    elif 'opera' in low or 'opr' in low:
        br = 'Opera'
    elif 'yandex' in low:
        br = 'Yandex'
    return dev, br, os


def track_visit():
    global _visit_counter, _visit_batch
    if request.path.startswith('/stone/api/') or request.path.startswith('/stone/admin/api/'):
        return
    if _is_bot():
        return
    ip = request.remote_addr or '0.0.0.0'

    # Rate-limit: max 1 visit per IP per VISIT_IP_COOLDOWN seconds
    now = time.time()
    if ip in _visit_ip_times and now - _visit_ip_times[ip] < VISIT_IP_COOLDOWN:
        return
    _visit_ip_times[ip] = now

    is_webapp = '/webapp' in request.path or session.get('stone_is_webapp', False)
    source = 'webapp' if is_webapp else 'site'
    ua = request.headers.get('User-Agent', '')
    dev, br, os_ = _parse_ua(ua)
    _visit_batch.append(VisitorLog(
        ip=ip, path=request.path[:200], source=source,
        device=dev, browser=br, os=os_
    ))
    _visit_counter += 1
    if _visit_counter >= VISIT_BATCH_SIZE:
        try:
            db.session.add_all(_visit_batch)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.error("Failed to flush visit batch")
        _visit_batch = []
        _visit_counter = 0


ADMIN_SESSION_MAX_AGE = 14400  # 4 hours

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_PASSWORD_STONE:
            return jsonify({'error': 'Admin not configured'}), 503
        if not session.get('stone_admin_logged_in'):
            return redirect(url_for('stone.admin_login_page'))
        login_at = session.get('stone_admin_login_at', 0)
        if time.time() - login_at > ADMIN_SESSION_MAX_AGE:
            session.pop('stone_admin_logged_in', None)
            session.pop('stone_admin_login_at', None)
            return redirect(url_for('stone.admin_login_page'))
        return f(*args, **kwargs)
    return decorated
