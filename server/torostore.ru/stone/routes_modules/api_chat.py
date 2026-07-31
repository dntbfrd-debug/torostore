import logging
import re
from flask import jsonify, request
from stone.models import StoneProduct
from db import db, StoneChatMessage
from utils import rate_limit
from stone.config import BOT_TOKEN_STONE, SELLER_CHAT_ID, BASE_URL
from stone.routes import stone_bp
import requests

logger = logging.getLogger(__name__)

XSS_PATTERN = re.compile(r'<script.*?>|</script>|javascript:|on\w+\s*=', re.IGNORECASE)

def _sanitize(text, max_len=500):
    if not text:
        return ''
    text = str(text)[:max_len]
    text = XSS_PATTERN.sub('', text)
    return text.strip()

@stone_bp.route('/api/chat/<avito_id>', methods=['GET'])
def api_chat_get(avito_id):
    token = request.args.get('token', '')[:64]
    q = StoneChatMessage.query.filter_by(avito_id=avito_id[:64])
    if token:
        q = q.filter_by(session_token=token)
    msgs = q.order_by(StoneChatMessage.created_at.asc()).limit(50).all()
    return jsonify([m.to_dict() for m in msgs])


@stone_bp.route('/api/chat/<avito_id>', methods=['POST'])
@rate_limit(max_per_minute=30)
def api_chat_post(avito_id):
    avito_id = avito_id[:64]
    data = request.json
    if not data:
        return jsonify({'error': 'no data'}), 400
    message = data.get('message', '')
    if not message or not message.strip():
        return jsonify({'error': 'message required'}), 400
    product = StoneProduct.query.filter_by(avito_id=avito_id).first()
    if not product:
        return jsonify({'error': 'product not found'}), 404
    msg = StoneChatMessage(
        avito_id=avito_id,
        session_token=_sanitize(data.get('session_token', ''), 64),
        user_name=_sanitize(data.get('user_name', 'Гость'), 120),
        user_contact=_sanitize(data.get('user_contact', ''), 120),
        message=_sanitize(message, 500),
        is_owner=False
    )
    db.session.add(msg)
    db.session.commit()
    
    ptitle = product.title if product else avito_id
    total = StoneChatMessage.query.filter_by(avito_id=avito_id, is_owner=False).count()
    owner_msg = (
        f"{'🆕' if total==1 else '💬'} <b>Сообщение в чате</b>\n\n"
        f"👤 {msg.user_name}\n"
        f"📦 {ptitle}\n"
        f"💬 {msg.message[:200]}\n\n"
        f"🔗 <a href='{BASE_URL}/stone/#{avito_id}'>Открыть на сайте</a>\n"
        f"📝 Для ответа: <code>/r {avito_id} ваш ответ</code>"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
            json={
                "chat_id": SELLER_CHAT_ID,
                "text": owner_msg,
                "parse_mode": "HTML",
                "reply_markup": {
                    "inline_keyboard": [[
                        {"text": "💬 Ответить", "callback_data": f"reply_{avito_id}"},
                        {"text": "🔗 Сайт", "url": f"{BASE_URL}/stone/#{avito_id}"}
                    ]]
                }
            },
            timeout=5
        )
    except Exception:
        logger.error(f"Failed to notify seller for {avito_id}")
    
    return jsonify(msg.to_dict()), 201
