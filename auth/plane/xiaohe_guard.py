# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Read-path guard for Plane's hot list endpoints.

A rendering loop re-fetches the same handful of lists (workspace projects,
members, the bots page) hundreds of times a minute. Rate limiting contains it,
but the cheapest request is the one that never reaches the view. This
middleware gives those GETs:

* a short per-user response cache (default 3 s), so a runaway client touches
  Postgres at most once per cache window instead of once per request;
* an ``ETag`` on every response plus ``304 Not Modified`` on revalidation, so a
  well-behaved client that polls can skip the body;
* an ``X-Build-Id`` header on every API response, which makes "which build is
  this client talking to" answerable from a single curl.

Any non-GET request from the same identity bumps a generation counter, so a
mutation (create a bot, add a member) is never followed by a stale list.

Kill switch: ``XIAOHE_READ_CACHE_ENABLED=0``. TTL: ``XIAOHE_READ_CACHE_TTL``.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseNotModified

logger = logging.getLogger("plane.authentication")

BUILD_ID = os.environ.get("XIAOHE_BUILD_ID", "").strip()

_CACHEABLE_PATHS = tuple(
    re.compile(pattern)
    for pattern in (
        r"^/api/workspaces/[^/]+/projects/?$",
        r"^/api/workspaces/[^/]+/projects/details/?$",
        r"^/api/workspaces/[^/]+/members/?$",
        r"^/auth/xiaohe/bots/[^/]+/?$",
        r"^/auth/xiaohe/bots/[^/]+/assignable/?$",
        r"^/auth/xiaohe/pages/[^/]+/?$",
    )
)


def _enabled() -> bool:
    return os.environ.get(
        "XIAOHE_READ_CACHE_ENABLED", "1"
    ).strip().lower() not in ("0", "false", "no", "off")


def _ttl() -> int:
    try:
        value = int(os.environ.get("XIAOHE_READ_CACHE_TTL", "3"))
    except ValueError:
        return 3
    return value if value >= 0 else 3


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "ignore")).hexdigest()


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class XiaoheGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = None
        cache_key = None
        identity = self._identity(request)

        if identity:
            if request.method == "GET" and self._cacheable(request.path):
                cache_key = self._cache_key(request, identity)
                response = self._from_cache(request, cache_key)
            elif request.method != "GET":
                # Any write can change a cached list; retire it for this user.
                self._bump_generation(identity)

        if response is None:
            response = self.get_response(request)
            if (
                cache_key
                and response.status_code == 200
                and not getattr(response, "streaming", False)
            ):
                self._store(cache_key, response)

        if BUILD_ID:
            response["X-Build-Id"] = BUILD_ID
        return response

    @staticmethod
    def _cacheable(path: str) -> bool:
        return _enabled() and any(p.match(path) for p in _CACHEABLE_PATHS)

    @staticmethod
    def _identity(request) -> str | None:
        """A stable, non-reversible handle for the caller.

        Session cookie and API key are hashed so the cache key never carries a
        credential, and two users can never share a cache entry.
        """
        api_key = request.META.get("HTTP_X_API_KEY")
        if api_key:
            return "k:" + _digest(api_key)[:32]
        cookie_name = getattr(settings, "SESSION_COOKIE_NAME", "session-id")
        session_id = request.COOKIES.get(cookie_name)
        if session_id:
            return "s:" + _digest(session_id)[:32]
        return None

    def _cache_key(self, request, identity: str) -> str:
        generation = self._generation(identity)
        return "xiaohe:read:" + _digest(
            f"{identity}|{generation}|{request.get_full_path()}"
        )

    @staticmethod
    def _generation(identity: str) -> int:
        try:
            return int(cache.get(f"xiaohe:readgen:{identity}") or 0)
        except Exception:
            return 0

    @staticmethod
    def _bump_generation(identity: str) -> None:
        key = f"xiaohe:readgen:{identity}"
        try:
            try:
                cache.incr(key)
            except ValueError:
                cache.add(key, 1, 3600)
        except Exception:
            logger.exception("xiaohe read-cache generation bump failed")

    def _from_cache(self, request, cache_key: str) -> HttpResponse | None:
        try:
            payload = cache.get(cache_key)
        except Exception:
            logger.exception("xiaohe read-cache lookup failed")
            return None
        if not payload:
            return None
        etag, body, content_type = payload
        if request.headers.get("If-None-Match") == etag:
            response = HttpResponseNotModified()
        else:
            response = HttpResponse(body, content_type=content_type)
        response["ETag"] = etag
        self._set_revalidation_headers(response)
        return response

    def _store(self, cache_key: str, response) -> None:
        body = response.content
        etag = '"' + _digest_bytes(body)[:32] + '"'
        content_type = response.get("Content-Type", "application/json")
        ttl = _ttl()
        if ttl > 0:
            try:
                cache.set(cache_key, (etag, body, content_type), ttl)
            except Exception:
                logger.exception("xiaohe read-cache store failed")
        response["ETag"] = etag
        self._set_revalidation_headers(response)

    @staticmethod
    def _set_revalidation_headers(response) -> None:
        response["Cache-Control"] = "private, max-age=0, must-revalidate"
        response["Vary"] = "Cookie, X-Api-Key"
