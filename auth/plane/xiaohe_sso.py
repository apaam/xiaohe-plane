# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""xiaohe accounts SSO for Plane (authorization code + PKCE).

Endpoints:
    /auth/xiaohe/start/?next=/research/
    /auth/xiaohe/callback/
    /auth/xiaohe/logout/        (POST, clears both Plane and accounts sessions)

Accounts issues a one-time code and returns {user: {id, email, is_admin}}.
Plane links/creates a local user by email and writes a normal Django session.
For clients that require a subscription, accounts also returns
user.subscription.expires_at; the session is capped at that instant so a
lapsed plan cannot keep an old login alive. Local password auth remains
available as an API break-glass path but its web pages redirect to SSO.
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
from datetime import datetime, timezone

from django.contrib.auth import logout
from django.http import HttpResponseRedirect
from django.views.decorators.http import require_GET, require_POST

from plane.authentication.utils.login import user_login
from plane.db.models import Profile, User, Workspace

# Serve Page images inline; keep the download behaviour for attachments.
from . import asset_inline_patch  # noqa: F401

logger = logging.getLogger(__name__)

ACCOUNTS_URL = os.environ.get(
    "XIAOHE_ACCOUNTS_URL", "https://accounts.xiaohe.team"
).rstrip("/")
CLIENT_ID = os.environ.get("XIAOHE_OAUTH_CLIENT_ID", "plane")
REDIRECT_URI = os.environ.get(
    "XIAOHE_OAUTH_REDIRECT",
    "https://plane.xiaohe.team/auth/xiaohe/callback/",
)
# Empty means “no deep link”: resolve the user's own last/first workspace.
DEFAULT_NEXT = ""
ONBOARDING_NEXT = "/onboarding/"
DEFAULT_TIMEZONE = os.environ.get("XIAOHE_DEFAULT_TIMEZONE", "Asia/Shanghai")
PLANE_HOME = os.environ.get("XIAOHE_PLANE_HOME", "https://plane.xiaohe.team/")

# Optional comma-separated aliases: accounts-email=plane-email.
# Example: some@example.com=alias@example.com
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


def _default_workspace_path(user: User) -> str:
    """Where a user lands when the caller did not ask for a specific page.

    Prefer the workspace they last visited (if they still belong to it), then
    the first workspace they belong to. New users have neither and go to
    onboarding, where they can create their own workspace or accept an invite.
    """
    profile = Profile.objects.filter(user=user).first()
    workspace = None
    if profile and profile.last_workspace_id:
        workspace = Workspace.objects.filter(
            id=profile.last_workspace_id,
            workspace_member__member=user,
            workspace_member__is_active=True,
        ).first()
    if workspace is None:
        workspace = (
            Workspace.objects.filter(
                workspace_member__member=user,
                workspace_member__is_active=True,
            )
            .order_by("created_at")
            .first()
        )
    return f"/{workspace.slug}/" if workspace is not None else ONBOARDING_NEXT


def _redirect_error() -> HttpResponseRedirect:
    # Do not bounce through /sign-in: that route now redirects to SSO, so a
    # failed callback would loop. Send the browser to the accounts login page
    # instead; the user can retry Plane from the apps portal.
    return HttpResponseRedirect(f"{ACCOUNTS_URL}/login?error=sso")


@require_POST
def xiaohe_logout(request):
    """Sign out of Plane, then out of accounts.

    Clearing only the Plane session is not enough: the next request would hit
    SSO and sign the browser straight back in from the still-live accounts
    session, which looks like sign-out did nothing.
    """
    logout(request)
    next_url = urllib.parse.quote(PLANE_HOME, safe="")
    return HttpResponseRedirect(f"{ACCOUNTS_URL}/logout?next={next_url}")


@require_GET
def xiaohe_start(request):
    next_path = _safe_next(request.GET.get("next"))
    if request.user.is_authenticated:
        return HttpResponseRedirect(next_path or _default_workspace_path(request.user))

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
    return data


def _unique_username(email: str) -> str:
    base = email.split("@", 1)[0][:30] or "xiaohe"
    candidate = base
    index = 1
    while User.objects.filter(username=candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _subscription_expiry(value: object) -> datetime | None:
    """Parse the accounts subscription claim; None means the claim is absent.

    A present but malformed or inactive claim is rejected by the caller. The
    claim is optional so an older accounts deployment (which still gates at
    authorize time) does not lock every user out during a rolling upgrade.
    """
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("active") is not True:
        raise ValueError("subscription is not active")
    raw = value.get("expires_at")
    if not isinstance(raw, str):
        raise ValueError("subscription expiry missing")
    try:
        expires_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("subscription expiry invalid") from exc
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at


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

    data = _exchange(code, verifier)
    if data is None:
        return _redirect_error()

    user_info = data.get("user")
    if not isinstance(user_info, dict):
        return _redirect_error()
    try:
        expires_at = _subscription_expiry(data.get("subscription"))
    except ValueError:
        return _redirect_error()
    if expires_at is not None and expires_at <= datetime.now(timezone.utc):
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
            user_timezone=DEFAULT_TIMEZONE,
        )
        user.set_unusable_password()
        user.save()
    elif not user.is_active:
        return _redirect_error()

    # A deep link (invitation, billing settings, etc.) wins. Otherwise use the
    # user's own last/first workspace, or onboarding when they have none.
    if not next_path or next_path == "/":
        next_path = _default_workspace_path(user)

    user.last_login_medium = "xiaohe"
    user.save(update_fields=["last_login_medium"])
    user_login(request=request, user=user, is_app=False)
    if expires_at is not None:
        seconds = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        request.session.set_expiry(max(1, seconds))
        request.session.save()
    return HttpResponseRedirect(next_path)
