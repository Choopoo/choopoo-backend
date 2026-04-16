import hashlib
import json
import redis


class RedisCache:
    def __init__(self, host, port):
        self.client = redis.Redis(host=host, port=int(port), decode_responses=True)

    def _make_key(self, url):
        # hash the URL so keys are uniform length
        return "page:" + hashlib.sha256(url.encode()).hexdigest()

    def get_cached(self, url):
        key = self._make_key(url)
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None

    def set_cache(self, url, value, ttl=300):
        key = self._make_key(url)
        self.client.setex(key, ttl, json.dumps(value))
