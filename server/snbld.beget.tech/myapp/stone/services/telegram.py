import logging
from flask import jsonify, request
from stone.models import StoneProduct
from models import db, StoneChatMessage
from utils import rate_limit
from stone.config import BOT_TOKEN_STONE, ADMIN_CHAT_ID, SELLER_CHAT_ID, TG_CHANNEL, TG_SELLER, BASE_URL
from stone.routes import stone_bp
import requests

logger = logging.getLogger(__name__)

# Set global default menu button (visible to all users, left of input)
try:
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/setChatMenuButton",
        json={"menu_button": {"type": "web_app", "text": "STORE", "web_app": {"url": f"{BASE_URL}/stone/webapp"}}},
        timeout=5
    )
except Exception:
    pass


@stone_bp.route('/webhook', methods=['POST'])
@rate_limit(max_per_minute=60)
def stone_webhook():
    data = request.get_json()
    if not data:
        return 'OK', 200

    # Handle inline button callbacks
    if 'callback_query' in data:
        cb = data['callback_query']
        cb_data = cb.get('data', '')
        cb_chat_id = str(cb['message']['chat']['id'])
        
        if cb_data.startswith('reply_'):
            avito_id = cb_data[6:]
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                json={
                    "chat_id": cb_chat_id,
                    "text": f"✏️ Введите ответ для товара {avito_id}:\n<code>/r {avito_id} ваш текст</code>",
                    "parse_mode": "HTML"
                },
                timeout=5
            )
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/answerCallbackQuery",
                json={"callback_query_id": cb['id'], "text": "Введите /r команду для ответа"},
                timeout=5
            )
        return 'OK', 200

    if 'message' in data:
        msg = data['message']
        chat_id = str(msg['chat']['id'])
        text = msg.get('text', '')
        
        # Seller commands
        if chat_id == ADMIN_CHAT_ID:
            # /r avito_id message
            if text.startswith('/r '):
                parts = text[3:].strip().split(maxsplit=1)
                if len(parts) == 2:
                    aid, reply_text = parts
                    # Find the session token for this avito_id
                    last_session = StoneChatMessage.query.filter_by(avito_id=aid.strip(), is_owner=False).order_by(StoneChatMessage.created_at.desc()).first()
                    stoken = last_session.session_token if last_session else ''
                    reply = StoneChatMessage(
                        avito_id=aid.strip(),
                        session_token=stoken,
                        user_name='Продавец',
                        message=reply_text[:500],
                        is_owner=True
                    )
                    db.session.add(reply)
                    db.session.commit()
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                        json={"chat_id": chat_id, "text": f"✅ Ответ отправлен в чат товара {aid}"},
                        timeout=5
                    )
                else:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                        json={"chat_id": chat_id, "text": "Формат: /r АЙДИ_ТОВАРА текст ответа"},
                        timeout=5
                    )
                return 'OK', 200
            
            # Plain text = reply to last active chat
            if text and not text.startswith('/'):
                last = StoneChatMessage.query.filter_by(is_owner=False).order_by(StoneChatMessage.created_at.desc()).first()
                if last:
                    reply = StoneChatMessage(
                        avito_id=last.avito_id,
                        session_token=last.session_token,
                        user_name='Продавец',
                        message=text[:500],
                        is_owner=True
                    )
                    db.session.add(reply)
                    db.session.commit()
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                        json={"chat_id": chat_id, "text": f"✅ Ответ в чат {last.avito_id}: {text[:50]}"},
                        timeout=5
                    )
                return 'OK', 200

        if text.startswith('/start buy_'):
            avito_id = text.split('buy_', 1)[1].strip().split()[0]
            
            try:
                sub_check = requests.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/getChatMember",
                    params={"chat_id": TG_CHANNEL, "user_id": chat_id},
                    timeout=5
                ).json()
                is_member = sub_check.get('result', {}).get('status') in ('member', 'administrator', 'creator', 'restricted')
            except Exception:
                is_member = False
            
            product = StoneProduct.query.filter_by(avito_id=avito_id, is_active=True).first()
            user_name = msg.get('from', {}).get('first_name', '') + ' ' + msg.get('from', {}).get('last_name', '')
            user_name = user_name.strip() or 'Пользователь'
            username = msg.get('from', {}).get('username', '')
            user_tag = '@' + username if username else user_name
            
            sub_icon = '✅' if is_member else '❌'
            sub_text = 'подписан' if is_member else 'НЕ ПОДПИСАН'
            
            if product:
                tg_link = f"tg://user?id={chat_id}"
                owner_msg = (
                    f"🛒 <b>ЗАПРОС НА ПОКУПКУ</b>\n\n"
                    f"{sub_icon} <b>{sub_text}</b> на канал {TG_CHANNEL}\n"
                    f"👤 {user_tag}\n"
                    f"📦 {product.title}\n"
                    f"💰 {product.price_string}\n\n"
                    f"🔗 <a href='{BASE_URL}/stone/#{avito_id}'>Карточка на сайте</a>\n"
                    f"📱 <a href='https://t.me/torostore_bot?startapp=item_{avito_id}'>Карточка в миниапп</a>\n"
                    f"💬 <a href='{tg_link}'>Написать покупателю</a>"
                )
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                    json={"chat_id": SELLER_CHAT_ID, "text": owner_msg, "parse_mode": "HTML"},
                    timeout=5
                )
                if not is_member:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": f"✅ Ваш запрос на <b>{product.title}</b> принят! С вами свяжется продавец.\n\n💡 Подпишитесь на <a href='https://t.me/{TG_CHANNEL.lstrip('@')}'>{TG_CHANNEL}</a> и получайте <b>бесплатную доставку</b>!\n\nПродавец: {TG_SELLER}",
                            "parse_mode": "HTML",
                            "reply_markup": {
                                "inline_keyboard": [[
                                    {"text": "📢 Подписаться на канал", "url": f"https://t.me/{TG_CHANNEL.lstrip('@')}"}
                                ]]
                            }
                        },
                        timeout=5
                    )
                else:
                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                        json={"chat_id": chat_id, "text": f"✅ Ваш запрос на <b>{product.title}</b> принят! С вами свяжется продавец.\n\n🎉 <b>Бесплатная доставка</b> активна!\n\nПродавец: {TG_SELLER}", "parse_mode": "HTML"},
                        timeout=5
                    )
            else:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                    json={"chat_id": chat_id, "text": "❌ Товар не найден."},
                    timeout=5
                )
        elif text.startswith('/start'):
            payload = {
                "chat_id": chat_id,
                "text": "Добро пожаловать в TORO STORE! Нажмите кнопку <b>STORE</b> слева от строки ввода для просмотра каталога.",
                "parse_mode": "HTML",
                "reply_markup": {"remove_keyboard": True}
            }
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/sendMessage",
                json=payload, timeout=5
            )
            # Set persistent menu button
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN_STONE}/setChatMenuButton",
                json={
                    "chat_id": chat_id,
                    "menu_button": {"type": "web_app", "text": "STORE", "web_app": {"url": f"{BASE_URL}/stone/webapp"}}
                },
                timeout=5
            )

    return 'OK', 200
