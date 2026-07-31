from flask import jsonify, request, render_template, session, redirect, url_for
from utils import rate_limit
from stone.config import ADMIN_PASSWORD_STONE
from stone.middleware import admin_required
from stone.routes import stone_bp
import secrets
import time

# ===== BRUTE FORCE PROTECTION =====
# In-memory store: {ip: {'count': N, 'locked_until': timestamp}}
_failed_attempts = {}
MAX_FAILED = 5
LOCKOUT_SECONDS = 900  # 15 minutes


def _is_locked_out(ip):
    entry = _failed_attempts.get(ip)
    if not entry:
        return False
    if entry.get('locked_until', 0) > time.time():
        return True
    # Lockout expired, clean up
    del _failed_attempts[ip]
    return False


def _record_failure(ip):
    entry = _failed_attempts.get(ip, {'count': 0, 'locked_until': 0})
    entry['count'] += 1
    if entry['count'] >= MAX_FAILED:
        entry['locked_until'] = time.time() + LOCKOUT_SECONDS
    _failed_attempts[ip] = entry


def _clear_failures(ip):
    _failed_attempts.pop(ip, None)


@stone_bp.route('/admin/login', methods=['GET', 'POST'])
@rate_limit(max_per_minute=5)
def admin_login_page():
    if not ADMIN_PASSWORD_STONE:
        return 'Admin panel not configured. Set ADMIN_PASSWORD env var.', 503
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        if _is_locked_out(ip):
            remaining = int(_failed_attempts[ip]['locked_until'] - time.time())
            return render_template('stone_admin_login.html', error=f'Слишком много попыток. Подождите {remaining // 60} мин {remaining % 60} сек.')
        pwd = request.form.get('password', '')
        if secrets.compare_digest(pwd, ADMIN_PASSWORD_STONE):
            _clear_failures(ip)
            session['stone_admin_logged_in'] = True
            session['stone_admin_login_at'] = time.time()
            return redirect(url_for('stone.catalog'))
        _record_failure(ip)
        remaining = MAX_FAILED - _failed_attempts[ip]['count']
        msg = f'Неверный пароль. Осталось попыток: {remaining}' if remaining > 0 else 'Слишком много попыток. Подождите 15 минут.'
        return render_template('stone_admin_login.html', error=msg)
    return render_template('stone_admin_login.html', error='')


@stone_bp.route('/admin/api/login', methods=['POST'])
@rate_limit(max_per_minute=10)
def admin_api_login():
    data = request.json or {}
    ip = request.remote_addr or 'unknown'
    if _is_locked_out(ip):
        return jsonify({'error': 'Слишком много попыток. Подождите 15 минут.'}), 429
    pwd = data.get('password', '')
    if secrets.compare_digest(pwd, ADMIN_PASSWORD_STONE):
        _clear_failures(ip)
        session['stone_admin_logged_in'] = True
        session['stone_admin_login_at'] = time.time()
        return jsonify({'success': True})
    _record_failure(ip)
    remaining = MAX_FAILED - _failed_attempts[ip]['count']
    msg = f'Неверный пароль. Осталось попыток: {remaining}' if remaining > 0 else 'Слишком много попыток. Подождите 15 минут.'
    return jsonify({'error': msg}), 401


@stone_bp.route('/admin/logout')
def admin_logout():
    session.pop('stone_admin_logged_in', None)
    session.pop('stone_admin_login_at', None)
    return redirect(url_for('stone.catalog'))
