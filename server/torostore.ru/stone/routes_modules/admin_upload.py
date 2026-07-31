import os as _os
import json
import secrets
import logging
from datetime import datetime
from flask import jsonify, request
from stone.models import StoneProduct
from models import db
from stone.config import IMAGE_THUMB_QUALITY, IMAGE_QUALITY
from stone.middleware import admin_required
from stone.routes import stone_bp

logger = logging.getLogger(__name__)


@stone_bp.route('/admin/api/upload', methods=['POST'])
@admin_required
def admin_api_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400
    files = request.files.getlist('file')
    if not files or not files[0].filename:
        return jsonify({'error': 'empty file'}), 400
    upload_dir = _os.path.join(_os.path.dirname(__file__), '..', '..', 'static', 'stone_imgs')
    _os.makedirs(upload_dir, exist_ok=True)
    uploaded = []
    ts = datetime.now().strftime('%y%m%d%H%M%S%f')
    rnd = secrets.token_hex(3)
    for i, f in enumerate(files):
        name = f'upload_{ts}_{rnd}_{i}.webp'
        name_thumb = f'upload_{ts}_{rnd}_{i}_thumb.webp'
        path = _os.path.join(upload_dir, name)
        path_thumb = _os.path.join(upload_dir, name_thumb)
        try:
            from PIL import Image
            img = Image.open(f.stream)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGBA')
            else:
                img = img.convert('RGB')
            thumb = img.copy()
            thumb.thumbnail((800, 800), Image.LANCZOS)
            thumb.save(path_thumb, 'WEBP', quality=IMAGE_THUMB_QUALITY, method=6)
            _os.chmod(path_thumb, 0o644)
            img.thumbnail((2000, 2000), Image.LANCZOS)
            img.save(path, 'WEBP', quality=IMAGE_QUALITY, method=6)
            _os.chmod(path, 0o644)
        except Exception:
            logger.error(f"Failed to process uploaded image {f.filename}")
            continue
        uploaded.append(f'/stone/media/{name_thumb.replace(".webp","")}')
    return jsonify({'success': True, 'urls': uploaded})


@stone_bp.route('/admin/api/bulk-images', methods=['POST'])
@admin_required
def admin_api_bulk_images():
    data = request.json or {}
    updated = 0
    for avito_id, images in data.items():
        p = StoneProduct.query.filter_by(avito_id=avito_id).first()
        if p and images:
            p.images = json.dumps(images, ensure_ascii=False)
            updated += 1
    db.session.commit()
    return jsonify({'success': True, 'updated': updated})
