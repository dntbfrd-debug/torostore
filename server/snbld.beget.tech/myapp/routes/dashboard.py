from flask import Blueprint, request, jsonify, render_template, send_file
from datetime import datetime, timedelta
import secrets
import os
import uuid
import json
import requests
from functools import wraps

from models import User, Employee, ShiftEntry, DailyRevenue, DailyNote, ArrivalNote, ArrivalPhoto, SpecialDay, ChatMessage, UserToken, RevisionNote, db
from utils import rate_limit
from app import basedir, BOT_TOKEN, GROUP_CHAT_ID, SCHEDULE_CHAT_ID, VK_API_TOKEN, VK_USER_ID, send_vk_message, upload_vk_photo

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')


def dashboard_auth_required(f):
    """Декоратор: проверяет токен в заголовке Authorization"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Требуется авторизация'}), 401
        token = auth[7:]
        user = User.query.filter_by(token=token).first()
        if not user or user.status != 'Активен' or not user.is_token_valid():
            ut = UserToken.query.filter_by(token=token).first()
            if not ut or not ut.is_valid():
                return jsonify({'error': 'Недействительный токен'}), 401
            user = ut.user
            if user.status != 'Активен':
                return jsonify({'error': 'Недействительный токен'}), 401
        return f(user=user, *args, **kwargs)
    return wrapped


@dashboard_bp.route('/dashboard/login')
def dashboard_login():
    return render_template('dashboard_login.html')


@dashboard_bp.route('/dashboard')
def dashboard_page():
    return render_template('dashboard_v4.html')


@dashboard_bp.route('/api/dashboard/register', methods=['POST'])
@rate_limit(max_per_minute=5)
def api_dashboard_register():
    data = request.json
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    if not name or not password:
        return jsonify({'error': 'Имя и пароль обязательны'}), 400
    if len(password) < 3:
        return jsonify({'error': 'Пароль должен быть минимум 3 символа'}), 400

    if User.query.filter_by(login=name).first():
        return jsonify({'error': 'Пользователь с таким именем уже существует'}), 400

    token = secrets.token_urlsafe(32)
    hwid = 'web_dashboard_' + secrets.token_hex(8)
    user = User(login=name, hwid=hwid, token=token, role='worker')
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    existing_emp = Employee.query.filter_by(name=name).first()
    if not existing_emp:
        emp = Employee(name=name, user_id=user.id)
        db.session.add(emp)

    db.session.commit()
    return jsonify({'success': True}), 201


@dashboard_bp.route('/api/dashboard/me', methods=['GET'])
@dashboard_auth_required
def api_dashboard_me(user):
    emp = Employee.query.filter_by(name=user.login).first()
    return jsonify({
        'login': user.login,
        'role': user.role or 'worker',
        'employee_id': emp.id if emp else None,
        'avatar': emp.avatar if emp else None,
    })


@dashboard_bp.route('/api/dashboard/change-password', methods=['POST'])
@dashboard_auth_required
def api_change_password(user):
    data = request.json
    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '')

    if not old_pw or not new_pw:
        return jsonify({'error': 'Оба поля обязательны'}), 400
    if len(new_pw) < 3:
        return jsonify({'error': 'Новый пароль должен быть минимум 3 символа'}), 400
    if not user.check_password(old_pw):
        return jsonify({'error': 'Неверный старый пароль'}), 400

    user.set_password(new_pw)
    db.session.commit()
    return jsonify({'success': True})


@dashboard_bp.route('/api/dashboard/login', methods=['POST'])
@rate_limit(max_per_minute=10)
def api_dashboard_login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400

    user = User.query.filter_by(login=username).first()
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    if user.status != 'Активен':
        return jsonify({'error': 'Аккаунт заблокирован'}), 403
    if not user.check_password(password):
        return jsonify({'error': 'Неверный пароль'}), 401

    if user.needs_hash_upgrade():
        user.set_password(password)
        db.session.flush()
        print(f'[PASS UPGRADE] {user.login}: SHA256 -> pbkdf2')

    token = secrets.token_urlsafe(32)
    ut = UserToken(user_id=user.id, token=token)
    db.session.add(ut)
    user.last_login = datetime.utcnow()
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f'[LOGIN COMMIT ERROR] {e}')
        return jsonify({'error': 'Ошибка сервера'}), 500

    return jsonify({'success': True, 'token': token, 'login': user.login})


@dashboard_bp.route('/api/dashboard/employees', methods=['GET'])
@dashboard_auth_required
def api_get_employees(user):
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.id).all()
    return jsonify([e.to_dict() for e in employees])


@dashboard_bp.route('/api/dashboard/employees', methods=['POST'])
@dashboard_auth_required
def api_add_employee(user):
    if user.role != 'admin':
        return jsonify({'error': 'Только админ может добавлять сотрудников'}), 403
    data = request.json
    name = data.get('name')
    if not name or not name.strip():
        return jsonify({'error': 'Имя сотрудника обязательно'}), 400

    existing = Employee.query.filter_by(name=name.strip()).first()
    if existing:
        return jsonify({'error': 'Сотрудник уже существует'}), 400

    emp = Employee(name=name.strip())
    db.session.add(emp)
    db.session.commit()
    return jsonify({'success': True, 'employee': emp.to_dict()}), 201


@dashboard_bp.route('/api/dashboard/employees/<int:emp_id>', methods=['DELETE'])
@dashboard_auth_required
def api_delete_employee(user, emp_id):
    if user.role != 'admin':
        return jsonify({'error': 'Только админ может удалять сотрудников'}), 403
    emp = Employee.query.get_or_404(emp_id)
    ShiftEntry.query.filter_by(employee_id=emp.id).delete()
    db.session.delete(emp)
    db.session.commit()
    return jsonify({'success': True})


@dashboard_bp.route('/api/dashboard/employees/<int:emp_id>/avatar', methods=['POST'])
@dashboard_auth_required
def api_upload_avatar(user, emp_id):
    emp = Employee.query.get_or_404(emp_id)
    file = request.files.get('avatar')
    if not file or not file.filename:
        return jsonify({'error': 'Файл не выбран'}), 400
    import uuid
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    if ext not in ('jpg', 'jpeg', 'png', 'webp'):
        ext = 'jpg'
    safe_name = f"av_{emp_id}_{uuid.uuid4().hex[:6]}.{ext}"
    base_dir = os.path.join(basedir, 'static', 'avatars')
    os.makedirs(base_dir, exist_ok=True)
    if emp.avatar:
        old = os.path.join(base_dir, emp.avatar)
        if os.path.exists(old):
            os.remove(old)
    file.save(os.path.join(base_dir, safe_name))
    emp.avatar = safe_name
    db.session.commit()
    return jsonify({'success': True, 'avatar': safe_name})


@dashboard_bp.route('/api/dashboard/employees/avatar-img')
def api_get_avatar():
    fn = request.args.get('file', '')
    if not fn: return '', 404
    fn = os.path.basename(fn)
    base_dir = os.path.join(basedir, 'static', 'avatars')
    fp = os.path.join(base_dir, fn)
    if not os.path.exists(fp): return '', 404
    if not os.path.realpath(fp).startswith(os.path.realpath(base_dir)): return '', 403
    return send_file(fp, mimetype='image/jpeg')


@dashboard_bp.route('/api/dashboard/schedule', methods=['GET'])
@dashboard_auth_required
def api_get_schedule(user):
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)

    if month < 1 or month > 12:
        return jsonify({'error': 'Некорректный месяц'}), 400

    shifts = ShiftEntry.query.filter(
        db.extract('year', ShiftEntry.date) == year,
        db.extract('month', ShiftEntry.date) == month
    ).all()

    return jsonify([s.to_dict() for s in shifts])


@dashboard_bp.route('/api/dashboard/schedule', methods=['POST'])
@rate_limit(max_per_minute=60)
@dashboard_auth_required
def api_save_schedule(user):
    data = request.json
    employee_id = data.get('employee_id')
    date_str = data.get('date')
    shift_type = data.get('shift_type')  # 'full', 'half', or None/'' to clear

    if not employee_id or not date_str:
        return jsonify({'error': 'employee_id и date обязательны'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты (нужен ГГГГ-ММ-ДД)'}), 400

    emp = Employee.query.get(employee_id)
    if not emp:
        return jsonify({'error': 'Сотрудник не найден'}), 404

    shift = ShiftEntry.query.filter_by(employee_id=employee_id, date=date_obj).first()

    if not shift_type or shift_type == '':
        if shift:
            db.session.delete(shift)
    else:
        if shift_type not in ('full', 'half'):
            return jsonify({'error': 'shift_type должен быть full, half или пустым'}), 400
        if shift:
            shift.shift_type = shift_type
            shift.updated_at = datetime.utcnow()
            shift.updated_by = user.id
        else:
            shift = ShiftEntry(
                employee_id=employee_id,
                date=date_obj,
                shift_type=shift_type,
                updated_by=user.id
            )
            db.session.add(shift)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Конфликт сохранения, попробуйте ещё раз'}), 409
    return jsonify({'success': True})


@dashboard_bp.route('/api/dashboard/summary', methods=['GET'])
@dashboard_auth_required
def api_dashboard_summary(user):
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)

    if month < 1 or month > 12:
        return jsonify({'error': 'Некорректный месяц'}), 400

    employees = Employee.query.filter_by(is_active=True).all()
    emp_ids = [e.id for e in employees]
    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date()
    else:
        last_day = datetime(year, month + 1, 1).date()
    
    all_shifts = ShiftEntry.query.filter(
        ShiftEntry.employee_id.in_(emp_ids),
        ShiftEntry.date >= first_day,
        ShiftEntry.date < last_day
    ).all()
    
    shifts_by_emp = {}
    for s in all_shifts:
        shifts_by_emp.setdefault(s.employee_id, []).append(s)

    result = []
    for emp in employees:
        shifts = shifts_by_emp.get(emp.id, [])
        full_count = sum(1 for s in shifts if s.shift_type == 'full')
        half_count = sum(1 for s in shifts if s.shift_type == 'half')
        total = full_count + half_count * 0.5
        result.append({
            'employee_id': emp.id,
            'employee_name': emp.name,
            'full_days': full_count,
            'half_days': half_count,
            'total_days': total,
        })
    return jsonify(result)


# ==================== DASHBOARD — ВЫРУЧКА И ЗАРПЛАТА ====================


@dashboard_bp.route('/api/dashboard/revenue', methods=['GET'])
@dashboard_auth_required
def api_get_revenue(user):
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)
    if month < 1 or month > 12:
        return jsonify({'error': 'Некорректный месяц'}), 400

    revenues = DailyRevenue.query.filter(
        db.extract('year', DailyRevenue.date) == year,
        db.extract('month', DailyRevenue.date) == month
    ).all()
    return jsonify([r.to_dict() for r in revenues])


@dashboard_bp.route('/api/dashboard/weather')
@rate_limit(max_per_minute=20)
def api_weather():
    try:
        url = 'https://api.open-meteo.com/v1/forecast'
        params = {
            'latitude': 45.009,
            'longitude': 39.055,
            'current_weather': 'true',
            'hourly': 'temperature_2m,precipitation_probability,weathercode',
            'timezone': 'auto'
        }
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        return jsonify(data)
    except Exception as e:
        print(f"[WEATHER ERROR] {type(e).__name__}: {e}")
        return jsonify({'error': str(e), 'type': type(e).__name__}), 502

@dashboard_bp.route('/api/dashboard/revenue', methods=['POST'])
@rate_limit(max_per_minute=30)
@dashboard_auth_required
def api_set_revenue(user):
    data = request.json
    date_str = data.get('date')
    amount = data.get('amount')

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400
    if amount is None:
        return jsonify({'error': 'amount обязателен'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'error': 'amount должен быть числом'}), 400
    rev = DailyRevenue.query.filter_by(date=date_obj).first()
    if rev:
        rev.amount = amount
        rev.last_edited_by = user.id
        rev.updated_at = datetime.utcnow()
    else:
        rev = DailyRevenue(date=date_obj, amount=amount, entered_by=user.id)
        db.session.add(rev)

    db.session.commit()
    return jsonify({'success': True, 'date': date_str, 'amount': amount})


@dashboard_bp.route('/api/dashboard/purchase', methods=['GET'])
@dashboard_auth_required
def api_get_purchase(user):
    date_str = request.args.get('date')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    if year and month:
        notes = DailyNote.query.filter(
            db.extract('year', DailyNote.date) == year,
            db.extract('month', DailyNote.date) == month
        ).all()
        return jsonify([n.to_dict() for n in notes])

    if not date_str:
        date_obj = datetime.utcnow().date()
    else:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Неверный формат даты'}), 400

    note = DailyNote.query.filter_by(date=date_obj).first()
    return jsonify(note.to_dict() if note else {'date': date_obj.isoformat(), 'text': ''})


@dashboard_bp.route('/api/dashboard/purchase', methods=['POST'])
@rate_limit(max_per_minute=30)
@dashboard_auth_required
def api_save_purchase(user):
    data = request.json
    date_str = data.get('date')
    text = data.get('text', '')

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:

        return jsonify({'error': 'Неверный формат даты'}), 400

    note = DailyNote.query.filter_by(date=date_obj).first()
    if note:
        note.text = text
        note.last_edited_by = user.id
        note.updated_at = datetime.utcnow()
    else:
        note = DailyNote(date=date_obj, text=text, created_by=user.id, last_edited_by=user.id)
        db.session.add(note)

    db.session.commit()
    return jsonify({'success': True, 'date': date_str, 'text': text})


@dashboard_bp.route('/api/dashboard/purchase/parse', methods=['POST'])
@rate_limit(max_per_minute=5)
@dashboard_auth_required
def api_parse_purchase(user):
    data = request.json
    raw_text = (data.get('text') or '').strip()
    if not raw_text:
        return jsonify({'error': 'Пустой текст'}), 400

    ds_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not ds_key:
        return jsonify({'error': 'API-ключ DeepSeek не настроен'}), 500

    try:
        resp = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Authorization': f'Bearer {ds_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {
                        'role': 'system',
                        'content': (
                            'Ты помощник для составления списков. Из текста (голосового или набранного) '
                            'выдели товары и количества. Верни ПРОНУМЕРОВАННЫЙ СПИСОК, '
                            'каждый товар с новой строки в формате: "1. Название товара — 2 шт". '
                            'Если количество не указано — пиши "1 шт". '
                            'Убирай лишние слова (вводные фразы, междометия). '
                            'Если текст не содержит товаров — верни "Товары не найдены". '
                            'НЕ пиши ничего кроме списка.'
                        ),
                    },
                    {'role': 'user', 'content': raw_text},
                ],
                'max_tokens': 600,
                'temperature': 0.1,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            err_msg = f'DeepSeek: HTTP {resp.status_code} - {resp.text[:200]}'
            with open('/home/s/snbld/snbld.beget.tech/tmp/parse_error.log', 'a') as f:
                f.write(f'{datetime.utcnow()} | {err_msg}\n')
            return jsonify({'error': err_msg}), 502
        body = resp.json()
        parsed = body['choices'][0]['message']['content'].strip()
        if not parsed:
            err_msg = f'Empty response from AI: {json.dumps(body, ensure_ascii=False)[:300]}'
            with open('/home/s/snbld/snbld.beget.tech/tmp/parse_error.log', 'a') as f:
                f.write(f'{datetime.utcnow()} | {err_msg}\n')
            return jsonify({'error': 'Пустой ответ от нейросети'}), 502
    except requests.exceptions.Timeout:
        err_msg = 'DeepSeek: таймаут запроса'
        with open('/home/s/snbld/snbld.beget.tech/tmp/parse_error.log', 'a') as f:
            f.write(f'{datetime.utcnow()} | {err_msg}\n')
        return jsonify({'error': err_msg}), 502
    except Exception as e:
        err_msg = f'DeepSeek: {type(e).__name__}: {e}'
        with open('/home/s/snbld/snbld.beget.tech/tmp/parse_error.log', 'a') as f:
            f.write(f'{datetime.utcnow()} | {err_msg}\n')
        return jsonify({'error': f'Ошибка парсинга: {type(e).__name__}'}), 502

    return jsonify({'success': True, 'text': parsed})


@dashboard_bp.route('/api/dashboard/purchase/send', methods=['POST'])
@dashboard_auth_required
def api_send_purchase_tg(user):
    data = request.json
    date_str = data.get('date', '')
    text = (data.get('text') or '').strip()

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400
    if not text:
        return jsonify({'error': 'Пустой текст закупа'}), 400

    bot_token = os.environ.get('BOT_TOKEN', '')
    chat_id = os.environ.get('GROUP_CHAT_ID', '')
    if not bot_token or not chat_id:
        return jsonify({'error': 'Telegram не настроен'}), 500

    # Сохраняем в БД если ещё нет
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        note = DailyNote.query.filter_by(date=date_obj).first()
        if note:
            note.text = text
            note.updated_at = datetime.utcnow()
        else:
            note = DailyNote(date=date_obj, text=text, created_by=user.id)
            db.session.add(note)
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    # Формируем сообщение
    msg = f'🛒 Закуп на {date_str}\n\n{text}\n\nОт: {user.login}'

    # Отправляем
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': chat_id, 'text': msg},
            timeout=10,
        )
        r.raise_for_status()
    except Exception as e:
        print(f'[TG SEND ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': f'Ошибка отправки: {str(e)}'}), 502

    return jsonify({'success': True, 'date': date_str})


@dashboard_bp.route('/api/dashboard/purchase/send-vk', methods=['POST'])
@dashboard_auth_required
def api_send_purchase_vk(user):
    data = request.json
    date_str = data.get('date', '')
    text = (data.get('text') or '').strip()

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400
    if not text:
        return jsonify({'error': 'Пустой текст закупа'}), 400

    vk_token = os.environ.get('VK_API_TOKEN', VK_API_TOKEN)
    vk_user_id = os.environ.get('VK_USER_ID', VK_USER_ID)
    if not vk_token or not vk_user_id:
        return jsonify({'error': 'VK не настроен'}), 500

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        note = DailyNote.query.filter_by(date=date_obj).first()
        if note:
            note.text = text
            note.updated_at = datetime.utcnow()
        else:
            note = DailyNote(date=date_obj, text=text, created_by=user.id)
            db.session.add(note)
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    msg = f'🛒 Закуп на {date_str}\n\n{text}\n\nОт: {user.login}'

    result = send_vk_message(vk_user_id, msg)
    if result is None:
        return jsonify({'error': 'Ошибка отправки в VK'}), 502

    return jsonify({'success': True, 'date': date_str})


# ── Arrivals (Приход продукции) ──

@dashboard_bp.route('/api/dashboard/arrivals', methods=['GET'])
@dashboard_auth_required
def api_get_arrivals(user):
    date_str = request.args.get('date')
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Неверный формат даты'}), 400
        note = ArrivalNote.query.filter_by(date=date_obj).first()
        return jsonify(note.to_dict() if note else {'date': date_str, 'text': '', 'photo_count': 0})

    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)
    notes = ArrivalNote.query.filter(
        db.extract('year', ArrivalNote.date) == year,
        db.extract('month', ArrivalNote.date) == month
    ).order_by(ArrivalNote.date.asc()).all()
    return jsonify([n.to_dict() for n in notes])


@dashboard_bp.route('/api/dashboard/arrivals', methods=['POST'])
@rate_limit(max_per_minute=30)
@dashboard_auth_required
def api_save_arrival(user):
    data = request.json
    date_str = data.get('date')
    text = data.get('text', '')

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    note = ArrivalNote.query.filter_by(date=date_obj).first()
    if note:
        note.text = text
        note.updated_at = datetime.utcnow()
    else:
        note = ArrivalNote(date=date_obj, text=text, created_by=user.id)
        db.session.add(note)

    db.session.commit()
    return jsonify(note.to_dict())


@dashboard_bp.route('/api/dashboard/arrivals/photos', methods=['POST'])
@dashboard_auth_required
def api_upload_arrival_photo(user):
    date_str = request.form.get('date')
    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    file = request.files.get('photo')
    if not file or not file.filename:
        return jsonify({'error': 'Файл не загружен'}), 400

    import uuid
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    if ext not in ('jpg', 'jpeg', 'png', 'webp', 'heic', 'heif'):
        ext = 'jpg'
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    base_dir = os.path.join(basedir, 'static', 'arrivals', date_str)
    os.makedirs(base_dir, exist_ok=True)
    filepath = os.path.join(base_dir, safe_name)
    file.save(filepath)

    note = ArrivalNote.query.filter_by(date=date_obj).first()
    if not note:
        note = ArrivalNote(date=date_obj, text='', created_by=user.id)
        db.session.add(note)
        db.session.flush()

    photo = ArrivalPhoto(arrival_id=note.id, filename=safe_name)
    db.session.add(photo)
    db.session.commit()

    return jsonify({
        'success': True,
        'filename': safe_name,
        'date': date_str,
        'photo_count': note.photos.count(),
    })


@dashboard_bp.route('/api/dashboard/arrivals/photos', methods=['DELETE'])
@dashboard_auth_required
def api_delete_arrival_photo(user):
    date_str = request.args.get('date', '')
    filename = request.args.get('file', '')
    if not date_str or not filename:
        return jsonify({'error': 'date и file обязательны'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    photo = ArrivalPhoto.query.filter_by(filename=filename).first()
    if not photo:
        return jsonify({'error': 'Фото не найдено'}), 404

    base_dir = os.path.join(basedir, 'static', 'arrivals', date_str)
    filepath = os.path.join(base_dir, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(photo)
    db.session.commit()

    note = ArrivalNote.query.filter_by(date=date_obj).first()
    return jsonify({
        'success': True,
        'photo_count': note.photos.count() if note else 0,
    })


@dashboard_bp.route('/api/dashboard/arrivals/photo')
@dashboard_auth_required
def api_get_arrival_photo(user):
    date_str = request.args.get('date', '')
    filename = request.args.get('file', '')
    if not date_str or not filename:
        return '', 404
    safe_date = os.path.basename(date_str)
    safe_file = os.path.basename(filename)
    base_dir = os.path.join(basedir, 'static', 'arrivals', safe_date)
    filepath = os.path.join(base_dir, safe_file)
    real_base = os.path.realpath(os.path.join(basedir, 'static', 'arrivals'))
    if not os.path.realpath(filepath).startswith(real_base):
        return '', 403
    if not os.path.exists(filepath):
        return '', 404
    return send_file(filepath)


@dashboard_bp.route('/api/dashboard/arrivals/send', methods=['POST'])
@dashboard_auth_required
def api_send_arrival_tg(user):
    data = request.json
    date_str = data.get('date', '')
    text = (data.get('text') or '').strip()

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400
    if not text:
        return jsonify({'error': 'Пустой текст прихода'}), 400

    bot_token = os.environ.get('BOT_TOKEN', '')
    chat_id = os.environ.get('GROUP_CHAT_ID', '')
    if not bot_token or not chat_id:
        return jsonify({'error': 'Telegram не настроен'}), 500

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        note = ArrivalNote.query.filter_by(date=date_obj).first()
        if note:
            note.text = text
            note.updated_at = datetime.utcnow()
        else:
            note = ArrivalNote(date=date_obj, text=text, created_by=user.id)
            db.session.add(note)
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    msg = f'📦 Приход на {date_str}\n\n{text}\n\nОт: {user.login}'

    try:
        r = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            json={'chat_id': chat_id, 'text': msg},
            timeout=10,
        )

        r.raise_for_status()
    except Exception as e:
        print(f'[TG SEND ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': f'Ошибка отправки: {str(e)}'}), 502

    # Отправляем фото
    photos_sent = 0
    if note:
        base_dir = os.path.join(basedir, 'static', 'arrivals', date_str)
        for p in note.photos.order_by(ArrivalPhoto.id).all():
            filepath = os.path.join(base_dir, p.filename)
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, 'rb') as f:
                    r = requests.post(
                        f'https://api.telegram.org/bot{bot_token}/sendPhoto',
                        data={'chat_id': chat_id},
                        files={'photo': (p.filename, f)},
                        timeout=30,
                    )
                    r.raise_for_status()
                photos_sent += 1
            except Exception as e:
                print(f'[TG PHOTO ERROR] {p.filename}: {e}')

    return jsonify({'success': True, 'date': date_str, 'photos_sent': photos_sent})


@dashboard_bp.route('/api/dashboard/arrivals/send-vk', methods=['POST'])
@dashboard_auth_required
def api_send_arrival_vk(user):
    data = request.json
    date_str = data.get('date', '')
    text = (data.get('text') or '').strip()

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400
    if not text:
        return jsonify({'error': 'Пустой текст прихода'}), 400

    vk_token = os.environ.get('VK_API_TOKEN', VK_API_TOKEN)
    vk_user_id = os.environ.get('VK_USER_ID', VK_USER_ID)
    if not vk_token or not vk_user_id:
        return jsonify({'error': 'VK не настроен'}), 500

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        note = ArrivalNote.query.filter_by(date=date_obj).first()
        if note:
            note.text = text
            note.updated_at = datetime.utcnow()
        else:
            note = ArrivalNote(date=date_obj, text=text, created_by=user.id)
            db.session.add(note)
        db.session.commit()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    msg = f'📦 Приход на {date_str}\n\n{text}\n\nОт: {user.login}'

    result = send_vk_message(vk_user_id, msg)
    if result is None:
        return jsonify({'error': 'Ошибка отправки в VK'}), 502

    photos_sent = 0
    if note:
        base_dir = os.path.join(basedir, 'static', 'arrivals', date_str)
        for p in note.photos.order_by(ArrivalPhoto.id).all():
            filepath = os.path.join(base_dir, p.filename)
            if not os.path.exists(filepath):
                continue
            try:
                attachment = upload_vk_photo(filepath)
                if attachment:
                    send_vk_message(vk_user_id, '', attachment=attachment)
                    photos_sent += 1
                else:
                    print(f'[VK PHOTO ERROR] {p.filename}: upload failed')
            except Exception as e:
                print(f'[VK PHOTO ERROR] {p.filename}: {e}')

    return jsonify({'success': True, 'date': date_str, 'photos_sent': photos_sent})


# ── Chat (дашборд-чатик, сообщения живут 12 часов) ──

@dashboard_bp.route('/api/dashboard/chat', methods=['GET'])
@dashboard_auth_required
def api_get_chat(user):
    cutoff = datetime.utcnow() - timedelta(hours=12)
    messages = ChatMessage.query.filter(ChatMessage.created_at >= cutoff)\
        .order_by(ChatMessage.created_at.asc()).all()
    return jsonify([m.to_dict() for m in messages])


@dashboard_bp.route('/api/dashboard/chat', methods=['POST'])
@rate_limit(max_per_minute=20)
@dashboard_auth_required
def api_send_chat(user):
    data = request.json
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Пустое сообщение'}), 400
    if len(text) > 500:
        return jsonify({'error': 'Максимум 500 символов'}), 400

    emp = Employee.query.filter_by(name=user.login).first()
    if not emp:
        return jsonify({'error': 'Сотрудник не найден'}), 404

    msg = ChatMessage(employee_id=emp.id, text=text)
    db.session.add(msg)
    db.session.commit()

    # Удаляем старые (>12ч) заодно
    cutoff = datetime.utcnow() - timedelta(hours=12)
    ChatMessage.query.filter(ChatMessage.created_at < cutoff).delete()
    db.session.commit()

    return jsonify(msg.to_dict())


# ── Schedule Screenshot ──

@dashboard_bp.route('/api/dashboard/schedule/send', methods=['POST'])
@dashboard_auth_required
def api_send_schedule_screenshot(user):
    if 'image' not in request.files:
        return jsonify({'error': 'Нет изображения'}), 400

    file = request.files['image']
    bot_token = os.environ.get('BOT_TOKEN', '')
    chat_id = os.environ.get('SCHEDULE_CHAT_ID', os.environ.get('GROUP_CHAT_ID', ''))

    if not bot_token or not chat_id:
        return jsonify({'error': 'Telegram не настроен'}), 500

    try:
        img_bytes = file.read()
        r = requests.post(
            f'https://api.telegram.org/bot{bot_token}/sendPhoto',
            data={'chat_id': chat_id, 'caption': f'📅 График смен — отправил: {user.login}'},
            files={'photo': (file.filename or 'schedule.png', img_bytes, file.content_type or 'image/png')},
            timeout=30,
        )
        if not r.json().get('ok'):
            err = r.json().get('description', str(r.text))
            print(f'[TG SCHEDULE SCREENSHOT ERROR] {err}')
            return jsonify({'error': err}), 502
    except Exception as e:
        print(f'[TG SCHEDULE SCREENSHOT ERROR] {type(e).__name__}: {e}')
        return jsonify({'error': str(e)}), 502

    return jsonify({'success': True})


# ── Special Days (праздники/больничные/отпуска) ──

@dashboard_bp.route('/api/dashboard/special-days', methods=['GET'])
@dashboard_auth_required
def api_get_special_days(user):
    year = request.args.get('year', type=int, default=datetime.utcnow().year)
    month = request.args.get('month', type=int, default=datetime.utcnow().month)
    days = SpecialDay.query.filter(
        db.extract('year', SpecialDay.date) == year,
        db.extract('month', SpecialDay.date) == month
    ).all()
    return jsonify([d.to_dict() for d in days])


@dashboard_bp.route('/api/dashboard/special-days', methods=['POST'])
@dashboard_auth_required
def api_set_special_day(user):
    if user.role != 'admin':
        return jsonify({'error': 'Только админ'}), 403

    data = request.json
    date_str = data.get('date')
    day_type = data.get('day_type', 'holiday')
    emp_id = data.get('employee_id')

    if not date_str or day_type not in ('holiday', 'sick', 'vacation'):
        return jsonify({'error': 'Неверные данные'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    existing = SpecialDay.query.filter_by(date=date_obj, employee_id=emp_id).first()
    if existing:
        if existing.day_type == day_type:
            # Удаляем если тот же тип (toggle off)
            db.session.delete(existing)
            db.session.commit()
            return jsonify({'success': True, 'removed': True})
        existing.day_type = day_type
    else:
        sd = SpecialDay(date=date_obj, day_type=day_type, employee_id=emp_id)
        db.session.add(sd)

    db.session.commit()
    return jsonify({'success': True})


# ── Revision (Лист ревизии) ──

@dashboard_bp.route('/api/dashboard/revisions', methods=['GET'])
@dashboard_auth_required
def api_get_revisions(user):
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if year and month:
        from calendar import monthrange
        last_day = monthrange(year, month)[1]
        start = f'{year}-{month:02d}-01'
        end = f'{year}-{month:02d}-{last_day}'
        notes = RevisionNote.query.filter(
            RevisionNote.date >= start, RevisionNote.date <= end
        ).order_by(RevisionNote.date.asc()).all()
    else:
        notes = RevisionNote.query.order_by(RevisionNote.date.desc()).limit(50).all()
    return jsonify([n.to_dict() for n in notes])


@dashboard_bp.route('/api/dashboard/revision/ai-parse', methods=['POST'])
@dashboard_auth_required
def api_revision_ai_parse(user):
    data = request.json
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Пустой текст'}), 400

    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'API-ключ не настроен'}), 500

    system_prompt = (
        "Ты — гений бухгалтер-ревизор. Твоя задача: из сырого списка товаров сделать идеальный лист ревизии.\n\n"
        "ПРАВИЛА:\n"
        "1. Определи категории в тексте. Категория — это строка без явного количества (например «Стаканы:», «Булочки —», «Сосиски:», «Вода:»). ВСЁ что идёт после категории до следующей категории — её подпозиции.\n"
        "2. Если товар вне категорий — помести в категорию «Общее».\n"
        "3. Арифметику считай (80+38=118). В qty бери ИТОГ.\n"
        "4. Единицы нормализуй строго:\n"
        "   - Штуки → 'X шт'\n"
        "   - Килограммы → 'X кг' (0,120→'0,12 кг', 1,650→'1,65 кг')\n"
        "   - Литры → 'X л' (11 л→'11 л')\n"
        "   - Граммы (число>100 без единиц) → 'X г'\n"
        "5. Если кол-во не указано — qty='—'\n"
        "6. Примечания в скобках сохраняй в qty\n"
        "7. НЕ придумывай, НЕ удаляй, НЕ объединяй позиции\n"
        "8. Порядок СТРОГО как в тексте\n\n"
        "Верни ТОЛЬКО JSON-массив объектов с категориями:\n"
        '[{"cat":"Название категории","items":[{"name":"Товар","qty":"100 шт"}]}]\n'
        'Если одна категория — всё равно массив с одним объектом.'
    )

    try:
        resp = requests.post(
            'https://api.deepseek.com/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': text},
                ],
                'max_tokens': 1500,
                'temperature': 0.1,
            },
            timeout=25,
        )
        if resp.status_code != 200:
            return jsonify({'error': f'AI HTTP {resp.status_code}'}), 502

        body = resp.json()
        raw = body['choices'][0]['message']['content'].strip()

        import re
        m = re.search(r'\[[\s\S]*\]', raw)
        if m:
            items = json.loads(m.group())
            return jsonify({'success': True, 'items': items, 'raw': raw})
        return jsonify({'error': 'AI не вернул JSON', 'raw': raw[:300]})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI таймаут'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/api/dashboard/revision/save', methods=['POST'])
@dashboard_auth_required
def api_save_revision(user):
    data = request.json
    date_str = data.get('date', '')
    text = (data.get('text') or '').strip()
    items = data.get('items', [])

    if not date_str:
        return jsonify({'error': 'date обязателен'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Неверный формат даты'}), 400

    note = RevisionNote.query.filter_by(date=date_obj).first()
    if note:
        note.text = text
        note.items_json = json.dumps(items, ensure_ascii=False)
        note.updated_at = datetime.utcnow()
    else:
        note = RevisionNote(
            date=date_obj, text=text,
            items_json=json.dumps(items, ensure_ascii=False),
            created_by=user.id
        )
        db.session.add(note)
    db.session.commit()
    return jsonify({'success': True, 'date': date_str, 'revision': note.to_dict()})
