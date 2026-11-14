"""Request rate limits and response security headers.

Limits are per demo session (customer or console cookie), falling back to the client
address, and apply only to state-changing requests. Speech calls have a tighter
budget because each one costs a live provider request. The in-memory window suits
this single-process demo; a deployment would use a shared store.
"""
import hashlib
import time
from collections import defaultdict, deque
from threading import Lock

DEFAULT_LIMITS = {'mutation': 120, 'speech': 12}  # Requests per rolling minute.
WINDOW = 60.0
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'",
    'Cross-Origin-Resource-Policy': 'same-origin',
}
MUTATING = {'POST', 'PUT', 'PATCH', 'DELETE'}


class RateLimiter:
    def __init__(self, limits):
        self.limits = limits
        self.hits = defaultdict(deque)
        self.lock = Lock()

    @staticmethod
    def identity(request):
        token = request.cookies.get('bytebot_session') or request.cookies.get('bytebot_console')
        raw = f'session:{token}' if token else f"address:{request.client.host if request.client else 'unknown'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]  # Never keep raw tokens in memory maps.

    def check(self, request):
        """Return seconds to wait when the request is over its budget, otherwise None."""
        if request.method not in MUTATING or not request.url.path.startswith('/api/'):
            return None
        bucket = 'speech' if request.url.path.endswith(('/voice', '/speak')) else 'mutation'
        key = (bucket, self.identity(request))
        now = time.monotonic()
        with self.lock:
            hits = self.hits[key]
            while hits and now - hits[0] > WINDOW:
                hits.popleft()
            if len(hits) >= self.limits[bucket]:
                return max(1, int(WINDOW - (now - hits[0])) + 1)
            hits.append(now)
        return None
