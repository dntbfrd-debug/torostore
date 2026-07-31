import time
from flask import request, jsonify
from functools import wraps

# ===== Rate Limiting (in-memory) =====
_rate_limit_store = {}

def rate_limit(max_per_minute=10):
    """Простой декоратор для ограничения частоты запросов по IP"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or 'unknown'
            now = time.time()
            key = f"{f.__name__}:{ip}"
            
            if key in _rate_limit_store:
                _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < 60]
            else:
                _rate_limit_store[key] = []
            
            if len(_rate_limit_store[key]) >= max_per_minute:
                return jsonify({'error': 'Слишком много запросов. Попробуйте через минуту.'}), 429
            
            _rate_limit_store[key].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator
