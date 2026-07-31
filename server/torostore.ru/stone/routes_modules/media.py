import os as _os
import re
from flask import send_from_directory, abort
from stone.routes import stone_bp

SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9_\-\.]+$')

def _is_safe_filename(filename):
    if not filename:
        return False
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    return bool(SAFE_FILENAME.match(filename))


@stone_bp.route('/static/stone_imgs/<path:filename>')
def stone_img(filename):
    if not _is_safe_filename(filename.rsplit('/', 1)[-1] if '/' in filename else filename):
        abort(400)
    return send_from_directory(_os.path.join(_os.path.dirname(__file__), '..', '..', 'static', 'stone_imgs'), filename)


@stone_bp.route('/media/<path:filename>')
def serve_stone_media(filename):
    img_dir = _os.path.join(_os.path.dirname(__file__), '..', '..', 'static', 'stone_imgs')
    basename = filename.rsplit('/', 1)[-1] if '/' in filename else filename
    if not _is_safe_filename(basename):
        abort(400)
    if not _os.path.splitext(filename)[1]:
        if _os.path.exists(_os.path.join(img_dir, filename + '.webp')):
            filename = filename + '.webp'
        elif _os.path.exists(_os.path.join(img_dir, filename + '.png')):
            filename = filename + '.png'
    return send_from_directory(img_dir, filename)
