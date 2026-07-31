import sys
import os
from datetime import datetime

basedir = '/home/s/snbld/snbld.beget.tech/myapp'
sys.path.insert(0, basedir)
os.chdir(basedir)

# === ЛОГИРОВАНИЕ (пишем в stderr, Passenger сохранит) ===
def log(msg, level='INFO'):
    print(f'{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} [{level}] TORO: {msg}', file=sys.stderr, flush=True)

log('Starting TORO STORE...')

# Переменные окружения
for varname in ("BOT_TOKEN", "BOT_TOKEN_STONE", "ADMIN_CHAT_ID", "SECRET_KEY",
                 "ADMIN_PASSWORD", "SELLER_CHAT_ID", "DEEPSEEK_API_KEY"):
    os.environ.setdefault(varname, os.environ.get(varname, ""))

from flask import Flask, redirect, request, g
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "users.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

from models import db, init_db
init_db(app)

from stone.routes import stone_bp
app.register_blueprint(stone_bp)

# === СТАТИЧЕСКИЕ РОУТЫ (шрифты, favicon) ===
from flask import send_file

@app.route('/font-saira')
def font_saira():
    return send_file(os.path.join(basedir, 'static', 'saira_stencil_one.ttf'), mimetype='font/ttf')

@app.route('/font-gi-stencil')
def font_gi():
    return send_file(os.path.join(basedir, 'static', 'gi_stencil_condensed_italic.ttf'), mimetype='font/ttf')

@app.route('/font-onest-400')
def font_onest_400():
    return send_file(os.path.join(basedir, 'static', 'onest-400.ttf'), mimetype='font/ttf')

@app.route('/font-onest-500')
def font_onest_500():
    return send_file(os.path.join(basedir, 'static', 'onest-500.ttf'), mimetype='font/ttf')

@app.route('/font-onest-600')
def font_onest_600():
    return send_file(os.path.join(basedir, 'static', 'onest-600.ttf'), mimetype='font/ttf')

@app.route('/font-onest-700')
def font_onest_700():
    return send_file(os.path.join(basedir, 'static', 'onest-700.ttf'), mimetype='font/ttf')

@app.route('/font-jetbrains-400')
def font_jb_400():
    return send_file(os.path.join(basedir, 'static', 'jetbrains-400.ttf'), mimetype='font/ttf')

@app.route('/font-jetbrains-500')
def font_jb_500():
    return send_file(os.path.join(basedir, 'static', 'jetbrains-500.ttf'), mimetype='font/ttf')

@app.route('/font-jetbrains-700')
def font_jb_700():
    return send_file(os.path.join(basedir, 'static', 'jetbrains-700.ttf'), mimetype='font/ttf')

@app.route('/font-russo-one')
def font_russo():
    return send_file(os.path.join(basedir, 'static', 'russo_one.ttf'), mimetype='font/ttf')

@app.route('/font-airport')
def font_airport():
    return send_file(os.path.join(basedir, 'static', 'airport.otf'), mimetype='font/otf')

@app.route('/font-inter-400')
def font_inter():
    return send_file(os.path.join(basedir, 'static', 'inter-400.ttf'), mimetype='font/ttf')

@app.route('/font-unbounded-400')
def font_unbounded():
    return send_file(os.path.join(basedir, 'static', 'unbounded-400.ttf'), mimetype='font/ttf')

@app.route('/font-blackops')
def font_blackops():
    return send_file(os.path.join(basedir, 'static', 'blackops.ttf'), mimetype='font/ttf')

@app.route('/favicon.ico')
def favicon_ico():
    fp = os.path.join(basedir, 'static', 'favicon.png')
    return send_file(fp, mimetype='image/x-icon')

@app.route('/stone-favicon')
def stone_favicon():
    fp = os.path.join(basedir, 'static', 'favicon.png')
    if os.path.exists(fp):
        return send_file(fp, mimetype='image/png')
    return send_file(os.path.join(basedir, 'static', 'bull_logo.jpg'), mimetype='image/jpeg')

# Статические файлы (лого, фон, изображения товаров)
@app.route('/brand-logo')
def brand_logo():
    return send_file(os.path.join(basedir, 'static', 'brand_logo.webp'), mimetype='image/webp')

@app.route('/toro-logo')
def toro_logo():
    return send_file(os.path.join(basedir, 'static', 'toro_logo.webp'), mimetype='image/webp')

@app.route('/si-bg')
def si_bg():
    return send_file(os.path.join(basedir, 'static', 'si_bg.webp'), mimetype='image/webp')

@app.route('/si-<path:filename>')
def si_image(filename):
    for ext in ['.jpg', '.webp', '.png', '']:
        fp = os.path.join(basedir, 'static', 'stone_imgs', f'{filename}{ext}')
        if os.path.exists(fp):
            return send_file(fp)
    # Fallback: try without index number
    base = filename.rsplit('_', 1)[0] if '_' in filename else filename
    for ext in ['.jpg', '.webp', '.png', '']:
        fp = os.path.join(basedir, 'static', 'stone_imgs', f'{base}{ext}')
        if os.path.exists(fp):
            return send_file(fp)
    return '', 404

@app.before_request
def log_request():
    g.start = time.time()

@app.after_request
def log_response(response):
    dt = (time.time() - g.get('start', 0)) * 1000
    if response.status_code >= 400:
        log(f'{request.method} {request.path} -> {response.status_code} ({dt:.0f}ms)', 'ERROR')
    return response

@app.route('/')
def index():
    return redirect('/stone/')

@app.route('/privacy')
def privacy():
    return send_file(os.path.join(basedir, 'privacy.html'))

@app.route('/terms')
def terms():
    return send_file(os.path.join(basedir, 'terms.html'))

log('TORO STORE ready')
application = app
