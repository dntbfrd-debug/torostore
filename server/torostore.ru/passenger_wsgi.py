import sys
import os
from datetime import datetime, timedelta

basedir = '/home/s/snbld/torostore.ru/app'
sys.path.insert(0, basedir)
os.chdir(basedir)

from flask import Flask, redirect, request, send_file, jsonify
from sqlalchemy import text
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "users.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)

# Import shared db (uses myapp's models.py since it's first in sys.path? No, basedir is first)
# Actually, we have our own copy of models.py in basedir. But models.py in basedir imports config
# which imports from config.py in basedir. Let's use our local copies.
from db import db, init_db
init_db(app)

# Register stone blueprint
from stone.routes import stone_bp
app.register_blueprint(stone_bp)

# Root redirect
@app.route('/')
def index():
    return redirect('/stone/')

# Font routes
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

@app.route('/font-cattedrale')
def font_cattedrale():
    return send_file(os.path.join(basedir, 'static', 'cattedrale.ttf'), mimetype='font/ttf')

@app.route('/font-manrope')
def font_manrope():
    return send_file(os.path.join(basedir, 'static', 'manrope.ttf'), mimetype='font/ttf')

@app.route('/favicon.ico')
def favicon_ico():
    return send_file(os.path.join(basedir, 'static', 'favicon.png'), mimetype='image/x-icon')

@app.route('/stone-favicon')
def stone_favicon():
    fp = os.path.join(basedir, 'static', 'favicon.png')
    if os.path.exists(fp):
        return send_file(fp, mimetype='image/png')
    return send_file(os.path.join(basedir, 'static', 'bull_logo.jpg'), mimetype='image/jpeg')

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
    base = filename.rsplit('_', 1)[0] if '_' in filename else filename
    for ext in ['.jpg', '.webp', '.png', '']:
        fp = os.path.join(basedir, 'static', 'stone_imgs', f'{base}{ext}')
        if os.path.exists(fp):
            return send_file(fp)
    return '', 404

@app.route('/privacy')
def privacy():
    return send_file(os.path.join(basedir, 'privacy.html'))

@app.route('/terms')
def terms():
    return send_file(os.path.join(basedir, 'terms.html'))

@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'db': 'ok'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'db': str(e)}), 503

application = app
