# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Per-user rate limiting for the Plane API.

A client that renders in a loop (or an old cached bundle that does) can issue
thousands of authenticated requests per minute and take the whole instance
down with it. DRF's stock ``AnonRateThrottle`` exempts authenticated callers,
so before this module there was no ceiling at all on a signed-in session.

Two throttles cover the two traffic shapes:

* ``XiaoheUserThrottle`` — a human session.
* ``XiaoheBotThrottle``  — a bot account or any caller using ``X-Api-Key``.

Both are token buckets kept in Redis (shared by every gunicorn worker; an
in-memory bucket per worker would multiply the limit by four). Exceeding the
ceiling returns 429 with ``Retry-After`` through DRF's normal ``Throttled``
path. Each bucket also counts the current wall-clock minute and logs a warning
when a caller crosses ``XIAOHE_RATE_WARN_PER_MIN``, so a misbehaving client is
visible in the logs before it becomes an incident.

Both throttles can be switched off at runtime with
``XIAOHE_THROTTLE_ENABLED=0`` without rebuilding the image.
"""

from __future__ import annotations

import logging
import os
import time
from functools import lru_cache

from rest_framework.throttling import BaseThrottle

from plane.settings.redis import redis_instance

logger = logging.getLogger("plane.authentication")

BOT_EMAIL_SUFFIX = "-bot@xiaohe.local"

# One bucket update and the per-minute counter increment in a single round
# trip. Clock comes from the Redis server so every worker sees the same time.
_LUA_CONSUME = """
local key = KEYS[1]
local minute_key = KEYS[2]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])

local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil or ts == nil then
  tokens = burst
  ts = now
end

local elapsed = now - ts
if elapsed < 0 then elapsed = 0 end
tokens = math.min(burst, tokens + elapsed * rate)

local allowed = 0
local wait_ms = 0
if tokens >= 1 then
  allowed = 1
  tokens = tokens - 1
else
  wait_ms = math.ceil((1 - tokens) * 1000 / rate)
end

redis.call('HSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(burst / rate) + 60)

local minute = redis.call('INCR', minute_key)
if minute == 1 then
  redis.call('EXPIRE', minute_key, 70)
end

return {allowed, wait_ms, minute}
"""

@lru_cache(maxsize=1)
def _client():
    """One pooled Redis client and one registered script for the process."""
    conn = redis_instance()
    return conn, conn.register_script(_LUA_CONSUME)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _enabled() -> bool:
    return os.environ.get("XIAOHE_THROTTLE_ENABLED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def is_bot_request(request) -> bool:
    """True for API-key callers and bot accounts (``*@xiaohe.local``)."""
    if request.META.get("HTTP_X_API_KEY"):
        return True
    email = (getattr(getattr(request, "user", None), "email", "") or "").lower()
    return email.endswith(BOT_EMAIL_SUFFIX)


class XiaoheBucketThrottle(BaseThrottle):
    """Shared token-bucket implementation; subclasses pick who they apply to."""

    scope = "xiaohe_user"
    rate_env = "XIAOHE_USER_RATE"
    rate_default = 5.0
    burst_env = "XIAOHE_USER_BURST"
    burst_default = 40

    def applies(self, request, user) -> bool:  # pragma: no cover - overridden
        raise NotImplementedError

    def allow_request(self, request, view) -> bool:
        if not _enabled():
            return True
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            # Anonymous callers stay under AnonRateThrottle.
            return True
        if not self.applies(request, user):
            return True

        rate = _env_float(self.rate_env, self.rate_default)
        burst = int(_env_int(self.burst_env, self.burst_default))
        minute = int(time.time() // 60)
        key = f"xiaohe:tb:{self.scope}:{user.id}"
        minute_key = f"xiaohe:rpm:{self.scope}:{user.id}:{minute}"
        try:
            conn, script = _client()
            allowed, wait_ms, count = script(
                keys=[key, minute_key], args=[rate, burst]
            )
        except Exception:  # Redis down or script error: fail open, never 500
            logger.exception("xiaohe throttle unavailable, failing open")
            return True

        self._wait = max(0.0, float(wait_ms) / 1000.0)
        self._log_rate(user, request, int(count))
        return bool(allowed)

    def _log_rate(self, user, request, count: int) -> None:
        warn_at = _env_int("XIAOHE_RATE_WARN_PER_MIN", 300)
        if count == warn_at + 1:
            logger.warning(
                "xiaohe high request rate user=%s path=%s count=%s/min scope=%s",
                user.id,
                request.path,
                count,
                self.scope,
            )
        elif count > warn_at and count % 200 == 0:
            logger.warning(
                "xiaohe sustained request rate user=%s path=%s count=%s/min scope=%s",
                user.id,
                request.path,
                count,
                self.scope,
            )

    def wait(self) -> float | None:
        return getattr(self, "_wait", None)


class XiaoheUserThrottle(XiaoheBucketThrottle):
    """Human sessions: sustained 5 req/s, burst 40 (env-tunable).

    The burst is deliberately larger than the sustained rate: a single settings
    page load fans out to a handful of requests, and a burst of 20 can trip
    mid-render, which reads to the user as a broken page rather than a limit.
    """

    scope = "xiaohe_user"

    def applies(self, request, user) -> bool:  # noqa: ARG002
        return not is_bot_request(request)


class XiaoheBotThrottle(XiaoheBucketThrottle):
    """Bots and API-key callers: sustained 2 req/s, burst 20.

    The sustained rate follows the plane-bridge polling cadence; it is a
    backstop for a stuck bridge, not a normal-operation limit.
    """

    scope = "xiaohe_bot"
    rate_env = "XIAOHE_BOT_RATE"
    rate_default = 2.0
    burst_env = "XIAOHE_BOT_BURST"
    burst_default = 20

    def applies(self, request, user) -> bool:  # noqa: ARG002
        return is_bot_request(request)


__all__ = [
    "XiaoheUserThrottle",
    "XiaoheBotThrottle",
    "is_bot_request",
]
