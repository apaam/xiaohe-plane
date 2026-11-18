# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Bot ownership guard for work-item assignment.

A bot may only be assigned by its owner or by a workspace admin. Ownership is
stored on the bot's active API token description as ``owner=<user_id>``; bots
without an owner marker are admin-only.
"""

from __future__ import annotations

import re

from rest_framework.exceptions import PermissionDenied

from plane.db.models import APIToken, User, WorkspaceMember

OWNER_RE = re.compile(r"owner=([0-9a-fA-F-]{36})")
BOT_SUFFIX = "-bot@xiaohe.local"
ADMIN_ROLE = 20


def bot_owner_id(bot_id) -> str | None:
    token = (
        APIToken.objects.filter(user_id=bot_id, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if token is None:
        return None
    match = OWNER_RE.search(token.description or "")
    return match.group(1) if match else None


def set_bot_owner(bot: User, owner_id) -> None:
    """Record the owner on every active token (rotation keeps the marker)."""
    marker = f"owner={owner_id}"
    for token in APIToken.objects.filter(user=bot, is_active=True):
        description = token.description or "xiaohe bot token"
        description = OWNER_RE.sub(marker, description)
        if marker not in description:
            description = f"{description}; {marker}"
        token.description = description
        token.save(update_fields=["description"])


def ensure_assignees_allowed(
    request,
    workspace_id,
    assignee_ids,
    default_assignee_id=None,
) -> None:
    if request is None:
        return
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return
    ids = [str(value) for value in (assignee_ids or [])]
    if not ids and default_assignee_id:
        ids = [str(default_assignee_id)]
    if not ids:
        return
    bots = list(
        User.objects.filter(id__in=ids, email__endswith=BOT_SUFFIX)
    )
    if not bots:
        return
    member = WorkspaceMember.objects.filter(
        workspace_id=workspace_id, member=user, is_active=True
    ).first()
    if member is not None and member.role >= ADMIN_ROLE:
        return
    for bot in bots:
        owner_id = bot_owner_id(bot.id)
        if owner_id and str(owner_id) == str(user.id):
            continue
        raise PermissionDenied(
            f"{bot.display_name} 只能由它的归属人或 workspace 管理员分配"
        )
