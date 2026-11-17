"""xiaohe accounts SSO for Plane (authorization code + PKCE).

Two GET endpoints:
    /auth/xiaohe/start/?next=/research/
    /auth/xiaohe/callback/

Accounts issues a one-time code and returns {user: {id, email, is_admin}}.
Plane links/creates a local user by email and writes a normal Django session.
Local password login remains available as a break-glass path.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET

from plane.authentication.utils.login import user_login
from plane.db.models import User

logger = logging.getLogger(__name__)

ACCOUNTS_URL = os.environ.get(
    "XIAOHE_ACCOUNTS_URL", "https://accounts.xiaohe.team"
).rstrip("/")
CLIENT_ID = os.environ.get("XIAOHE_OAUTH_CLIENT_ID", "plane")
REDIRECT_URI = os.environ.get(
    "XIAOHE_OAUTH_REDIRECT",
    "https://plane.xiaohe.team/auth/xiaohe/callback/",
)
DEFAULT_NEXT = "/research/"

# Optional comma-separated aliases: accounts-email=plane-email.
# Example: lai.zhengshou@outlook.com=laizhengsh@mail.sysu.edu.cn
EMAIL_MAP: dict[str, str] = {}
for _pair in os.environ.get("XIAOHE_SSO_EMAIL_MAP", "").split(","):
    if "=" in _pair:
        _source, _target = _pair.split("=", 1)
        if _source.strip() and _target.strip():
            EMAIL_MAP[_source.strip().lower()] = _target.strip().lower()

SESSION_VERIFIER = "xiaohe_oauth_verifier"
SESSION_STATE = "xiaohe_oauth_state"
SESSION_NEXT = "xiaohe_oauth_next"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _challenge(verifier: str) -> str:
    return _b64url(hashlib.sha256(verifier.encode("ascii")).digest())


def _safe_next(value: str | None) -> str:
    if not value:
        return DEFAULT_NEXT
    value = value.strip()
    if not value.startswith("/") or value.startswith("//"):
        return DEFAULT_NEXT
    return value


def _redirect_error() -> HttpResponseRedirect:
    return HttpResponseRedirect("/sign-in/?error=sso")


@require_GET
def xiaohe_start(request):
    next_path = _safe_next(request.GET.get("next"))
    if request.user.is_authenticated:
        return HttpResponseRedirect(next_path)

    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(32)
    request.session[SESSION_VERIFIER] = verifier
    request.session[SESSION_STATE] = state
    request.session[SESSION_NEXT] = next_path
    request.session.save()

    query = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return HttpResponseRedirect(f"{ACCOUNTS_URL}/oauth/authorize?{query}")


def _exchange(code: str, verifier: str) -> dict | None:
    payload = json.dumps(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
        }
    ).encode("utf-8")
    token_request = urllib.request.Request(
        f"{ACCOUNTS_URL}/v1/oauth/token",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(token_request, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.HTTPError,
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        logger.warning("xiaohe sso token exchange failed: %s", exc)
        return None

    user = data.get("user") if isinstance(data, dict) else None
    if not isinstance(user, dict):
        return None
    email = user.get("email")
    if not isinstance(email, str) or "@" not in email:
        return None
    return user


def _unique_username(email: str) -> str:
    base = email.split("@", 1)[0][:30] or "xiaohe"
    candidate = base
    index = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


@require_GET
def xiaohe_callback(request):
    error = request.GET.get("error")
    code = request.GET.get("code", "").strip()
    state = request.GET.get("state", "").strip()
    expected_state = request.session.pop(SESSION_STATE, "")
    verifier = request.session.pop(SESSION_VERIFIER, "")
    next_path = _safe_next(request.session.pop(SESSION_NEXT, DEFAULT_NEXT))
    request.session.save()

    if error or not code or not state or not expected_state or not verifier:
        return _redirect_error()
    if not hmac.compare_digest(state, expected_state):
        return _redirect_error()

    user_info = _exchange(code, verifier)
    if user_info is None:
        return _redirect_error()

    email = str(user_info["email"]).strip().lower()
    email = EMAIL_MAP.get(email, email)
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create(
            email=email,
            username=_unique_username(email),
            display_name=email.split("@", 1)[0],
            first_name="",
            last_name="",
            is_active=True,
            is_email_verified=True,
            is_password_autoset=True,
        )
        user.set_unusable_password()
        user.save()
    elif not user.is_active:
        return _redirect_error()

    user.last_login_medium = "xiaohe"
    user.save(update_fields=["last_login_medium"])
    user_login(request=request, user=user, is_app=False)
    return HttpResponseRedirect(next_path)
