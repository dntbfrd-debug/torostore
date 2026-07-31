import os as _os
from flask import send_from_directory
from stone.routes import stone_bp


@stone_bp.route('/static/stone_imgs/<path:filename>')
def stone_img(filename):
    return send_from_directory(_os.path.join(_os.path.dirname(__file__), '..', '..', 'static', 'stone_imgs'), filename)


@stone_bp.route('/media/<path:filename>')
def serve_stone_media(filename):
    img_dir = _os.path.join(_os.path.dirname(__file__), '..', '..', 'static', 'stone_imgs')
    if not _os.path.splitext(filename)[1]:
        if _os.path.exists(_os.path.join(img_dir, filename + '.webp')):
            filename = filename + '.webp'
        elif _os.path.exists(_os.path.join(img_dir, filename + '.png')):
            filename = filename + '.png'
    return send_from_directory(img_dir, filename)
