import time
import threading
from functools import wraps
from flask import request, jsonify


class AnalysisCache:
    def __init__(self, ttl=900):
        self._cache = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def get(self, key):
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() - entry["time"] < self._ttl:
                    return entry["data"]
                del self._cache[key]
        return None

    def set(self, key, data):
        with self._lock:
            self._cache[key] = {"data": data, "time": time.time()}

    def invalidate(self, key):
        with self._lock:
            self._cache.pop(key, None)

    def clear(self):
        with self._lock:
            self._cache.clear()


analysis_cache = AnalysisCache()


class RateLimiter:
    def __init__(self, max_requests=10, window=60):
        self._requests = {}
        self._lock = threading.Lock()
        self._max_requests = max_requests
        self._window = window

    def _get_key(self, identifier):
        now = time.time()
        with self._lock:
            if identifier not in self._requests:
                self._requests[identifier] = []
            timestamps = self._requests[identifier]
            timestamps = [t for t in timestamps if now - t < self._window]
            self._requests[identifier] = timestamps
            return len(timestamps)

    def is_allowed(self, identifier):
        count = self._get_key(identifier)
        if count >= self._max_requests:
            return False
        with self._lock:
            self._requests[identifier].append(time.time())
        return True


rate_limiter = RateLimiter()


def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = None
        from flask import session
        if "user_id" in session:
            user_id = str(session["user_id"])
        else:
            user_id = request.remote_addr or "unknown"

        if not rate_limiter.is_allowed(user_id):
            return jsonify({"error": "Rate limit exceeded. Please try again later."}), 429
        return f(*args, **kwargs)
    return decorated
