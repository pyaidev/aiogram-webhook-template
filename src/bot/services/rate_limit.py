from redis.asyncio import Redis

FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class RateLimiter:
    """Atomic shared fixed window; permits a bounded burst at a window boundary."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, key: str, *, limit: int, window: int) -> tuple[bool, int]:
        count, ttl = await self.redis.eval(FIXED_WINDOW_SCRIPT, 1, f"bot:rate:{key}", window)
        return count <= limit, max(int(ttl), 1)
