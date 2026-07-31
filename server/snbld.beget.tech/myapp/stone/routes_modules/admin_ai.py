import json
import re
import logging
import os
from flask import jsonify, request
from utils import rate_limit
from stone.middleware import admin_required
from stone.routes import stone_bp
import requests

logger = logging.getLogger(__name__)

OPENCODE_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'article_cache.json')


def _quick_search(query):
    """Search with cache"""
    art = re.search(r'\d{6,}', query)
    art = art.group() if art else query[:20]
    
    # Check cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.loads(open(CACHE_FILE).read())
        except Exception:
            pass
    
    if art in cache:
        logger.info(f"Cache hit for {art}")
        return cache[art]
    
    # Live search
    try:
        from ddgs import DDGS
        results = list(DDGS().text(f'stone island {query}', max_results=5))
        text = ' | '.join([r.get('body', '')[:200] for r in results if r.get('body')])[:2000]
        if text:
            cache[art] = text
            try:
                open(CACHE_FILE, 'w').write(json.dumps(cache, ensure_ascii=False, indent=2))
            except Exception:
                pass
        return text
    except Exception:
        pass
    return ''


def _decode_art(query):
    """Extract and decode Stone Island article number"""
    import re
    m = re.search(r'(\d{6,})', query)
    if not m:
        return ''
    art = m.group(1)
    # Stone Island article format: SSCCCPPP where SS=season, CCC=color/model, PPP=product
    season_map = {'22':'SPRING/SUMMER','23':'SPRING/SUMMER','42':'AUTUMN/WINTER','43':'AUTUMN/WINTER',
                  '52':'SPRING/SUMMER','53':'SPRING/SUMMER','56':'SPRING/SUMMER','57':'SPRING/SUMMER',
                  '62':'AUTUMN/WINTER','63':'AUTUMN/WINTER','65':'AUTUMN/WINTER','66':'AUTUMN/WINTER',
                  '67':'AUTUMN/WINTER','68':'AUTUMN/WINTER','69':'AUTUMN/WINTER',
                  '72':'SPRING/SUMMER','73':'SPRING/SUMMER','75':'SPRING/SUMMER','76':'SPRING/SUMMER',
                  '77':'AUTUMN/WINTER','78':'AUTUMN/WINTER','81':'AUTUMN/WINTER'}
    season_code = art[:2]
    season = season_map.get(season_code, '')
    year = '20' + art[:2] if art[:2].isdigit() else ''
    return f'\n\nРАСШИФРОВКА АРТИКУЛА:\nАртикул: {art}\nСезон: {season}\nГод: {year}\nВАЖНО: Определи ТИП ВЕЩИ (куртка/худи/свитер/штаны/аксессуар) по артикулу и результатам поиска. Если не уверен — укажи наиболее вероятный тип с оговоркой.\n'


@stone_bp.route('/admin/api/ai-search', methods=['POST'])
@admin_required
@rate_limit(max_per_minute=5)
def admin_api_ai_search():
    data = request.json or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Опишите товар: тип, цвет, материал. Например: куртка синяя nylon metal'}), 400

    system_prompt = (
        "Ты эксперт по Stone Island. Пиши ТОЛЬКО на русском.\n"
        "Админ передаёт описание или артикул товара. Твоя задача — написать точное продающее описание (3-5 предложений).\n"
        "ПРАВИЛА:\n"
        "1. ТОЧНО определи тип вещи по артикулу. Stone Island НЕ ДЕЛАЕТ худи/свитера из nylon metal — это только для курток.\n"
        "2. Если в данных поиска сказано 'hoodie' или 'sweatshirt' — это худи/свитшот, а НЕ куртка.\n"
        "3. Если артикул начинается на 5 — это скорее трикотаж (свитер/худи), на 4 или 6 — куртка/верхняя одежда.\n"
        "4. Не выдумывай материал если он не указан в данных поиска.\n"
        "Верни ТОЛЬКО JSON:\n"
        '{"title":"","description":""}'
    )

    user_msg = (
        f"Напиши описание для товара Stone Island. Админ описал его так: {query}\n\n"
        "Дай точное название (title) и описание (description 3-5 предложений на русском)."
    )
    
    # Add article decoding
    art_info = _decode_art(query)
    if art_info:
        user_msg += art_info
    
    # Quick search for additional context
    extra = _quick_search(query)
    if extra:
        user_msg += f"\nДАННЫЕ ИЗ ПОИСКА (используй эту информацию для определения типа вещи и деталей!):\n{extra[:1500]}"

    try:
        resp = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENCODE_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                'max_tokens': 4000,
                'temperature': 0.3,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            err = resp.json().get('error', {}).get('message', resp.text[:200])
            return jsonify({'error': f'AI: {err}'}), 502

        raw = resp.json()['choices'][0]['message'].get('content', '')
        if not raw:
            raw = resp.json()['choices'][0]['message'].get('reasoning_content', '')
        raw = (raw or '').strip()
        
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return jsonify({'success': True, 'data': json.loads(m.group())})
        try:
            return jsonify({'success': True, 'data': json.loads(raw)})
        except Exception:
            pass
        return jsonify({'error': 'AI не вернул JSON', 'raw': raw[:500]})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI таймаут'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500
