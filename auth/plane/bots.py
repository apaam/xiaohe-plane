# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Workspace-admin bot provisioning for Plane.

A bot is an ordinary Plane user (``is_bot=False`` so it stays selectable as an
assignee) whose email ends with ``-bot@xiaohe.local`` and which is backed by a
managed API token. Workspace admins can create, rotate and disable bots here
instead of running a Django shell inside the container.

Routes (mounted under ``/auth/`` by ``urls_xiaohe``):

    GET    /auth/xiaohe/bots/<slug>/
    POST   /auth/xiaohe/bots/<slug>/
    POST   /auth/xiaohe/bots/<slug>/<bot_id>/rotate/
    POST   /auth/xiaohe/bots/<slug>/<bot_id>/disable/
    POST   /auth/xiaohe/bots/<slug>/<bot_id>/enable/
"""

from __future__ import annotations

import logging
import re

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import (
    APIToken,
    Profile,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    User,
    Workspace,
    WorkspaceMember,
)

logger = logging.getLogger(__name__)

BOT_DOMAIN = "@xiaohe.local"
BOT_SUFFIX = "-bot" + BOT_DOMAIN
ADMIN_ROLE = 20
MEMBER_ROLE = 15


def _admin_workspace(slug: str, user):
    workspace = Workspace.objects.filter(slug=slug, workspace_member__member=user,
                                         workspace_member__is_active=True).first()
    if workspace is None:
        return None
    member = WorkspaceMember.objects.filter(
        workspace=workspace, member=user, is_active=True
    ).first()
    if member is None or member.role < ADMIN_ROLE:
        return None
    return workspace


def _bot_queryset(workspace):
    return User.objects.filter(
        member_workspace__workspace=workspace,
        email__endswith=BOT_SUFFIX,
    ).distinct()


def _bot_payload(bot: User, workspace, member: WorkspaceMember | None) -> dict:
    projects = list(
        ProjectMember.objects.filter(member=bot, project__workspace=workspace)
        .select_related("project")
        .values("project_id", "project__identifier", "project__name")
    )
    tokens = APIToken.objects.filter(user=bot, workspace=workspace)
    last_used = max(
        (token.last_used for token in tokens if token.last_used), default=None
    )
    return {
        "id": str(bot.id),
        "email": bot.email,
        "display_name": bot.display_name,
        "is_active": bool(member and member.is_active),
        "token_active": any(token.is_active for token in tokens),
        "last_used": last_used.isoformat() if last_used else None,
        "projects": [
            {
                "id": str(row["project_id"]),
                "identifier": row["project__identifier"],
                "name": row["project__name"],
            }
            for row in projects
        ],
    }


def _bot_email(name: str) -> str:
    local = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if local.endswith("-bot"):
        local = local[:-4]
    if not local:
        local = "team"
    return f"{local}{BOT_SUFFIX}"


def _validate_bot_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email.endswith(BOT_SUFFIX):
        raise ValueError(f"bot 邮箱必须以 {BOT_SUFFIX} 结尾")
    return email


class BotsView(APIView):
    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        workspace = _admin_workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "only workspace admins can manage bots"},
                status=status.HTTP_403_FORBIDDEN,
            )
        bots = _bot_queryset(workspace).order_by("display_name")
        members = {
            str(member.member_id): member
            for member in WorkspaceMember.objects.filter(
                workspace=workspace, member__in=bots
            )
        }
        return Response(
            {
                "bots": [
                    _bot_payload(bot, workspace, members.get(str(bot.id)))
                    for bot in bots
                ]
            }
        )

    @transaction.atomic
    def post(self, request, slug: str):
        workspace = _admin_workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "only workspace admins can manage bots"},
                status=status.HTTP_403_FORBIDDEN,
            )
        name = str(request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"error": "name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            email = _validate_bot_email(
                request.data.get("email") or _bot_email(name)
            )
        except ValueError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        if User.objects.filter(email=email).exists():
            return Response(
                {"error": f"{email} already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project_ids = [str(value) for value in request.data.get("project_ids") or []]
        projects = list(
            Project.objects.filter(
                workspace=workspace, id__in=project_ids
            )
        ) if project_ids else []

        first_name, _, last_name = name.partition(" ")
        username = re.sub(r"[^a-z0-9-]", "-", email.split("@")[0])[:30]
        bot = User.objects.create(
            email=email,
            username=username,
            display_name=name,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_email_verified=True,
            is_password_autoset=True,
            is_bot=False,
        )
        bot.set_unusable_password()
        bot.save(update_fields=["password"])
        WorkspaceMember.objects.create(
            workspace=workspace, member=bot, role=MEMBER_ROLE
        )
        profile, _ = Profile.objects.get_or_create(user=bot)
        profile.is_onboarded = True
        profile.last_workspace_id = workspace.id
        profile.save(update_fields=["is_onboarded", "last_workspace_id"])
        for project in projects:
            ProjectMember.objects.create(
                project=project, member=bot, role=MEMBER_ROLE
            )
        token = APIToken.objects.create(
            user=bot,
            workspace=workspace,
            user_type=1,
            label=f"{name} bot token",
            description="created from the workspace bots page",
        )
        logger.info("xiaohe bot created email=%s by=%s", email, request.user.email)
        member = WorkspaceMember.objects.filter(
            workspace=workspace, member=bot
        ).first()
        return Response(
            {
                "bot": _bot_payload(bot, workspace, member),
                "token": token.token,
            },
            status=status.HTTP_201_CREATED,
        )


class BotActionView(APIView):
    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, bot_id: str, action: str):
        workspace = _admin_workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "only workspace admins can manage bots"},
                status=status.HTTP_403_FORBIDDEN,
            )
        bot = _bot_queryset(workspace).filter(id=bot_id).first()
        if bot is None:
            return Response(
                {"error": "bot not found"}, status=status.HTTP_404_NOT_FOUND
            )
        member = WorkspaceMember.objects.filter(
            workspace=workspace, member=bot
        ).first()
        tokens = APIToken.objects.filter(user=bot, workspace=workspace)
        if action == "rotate":
            tokens.update(is_active=False)
            token = APIToken.objects.create(
                user=bot,
                workspace=workspace,
                user_type=1,
                label=f"{bot.display_name} bot token",
                description="rotated from the workspace bots page",
            )
            logger.info(
                "xiaohe bot rotated email=%s by=%s", bot.email, request.user.email
            )
            return Response({"token": token.token})
        if action == "disable":
            tokens.update(is_active=False)
            if member:
                member.is_active = False
                member.save(update_fields=["is_active"])
            ProjectMember.objects.filter(member=bot).update(is_active=False)
            bot.is_active = False
            bot.save(update_fields=["is_active"])
            logger.info(
                "xiaohe bot disabled email=%s by=%s", bot.email, request.user.email
            )
            return Response({"ok": True})
        if action == "enable":
            if member:
                member.is_active = True
                member.save(update_fields=["is_active"])
            ProjectMember.objects.filter(member=bot).update(is_active=True)
            bot.is_active = True
            bot.save(update_fields=["is_active"])
            logger.info(
                "xiaohe bot enabled email=%s by=%s", bot.email, request.user.email
            )
            return Response({"ok": True})
        return Response(
            {"error": "unknown action"}, status=status.HTTP_400_BAD_REQUEST
        )


class PagesView(APIView):
    """Read-only Pages access for bot tokens.

    The official v1 API (and the web app API) do not expose Pages to API-key
    callers. This endpoint fills that gap for public pages and for pages linked
    to projects the caller belongs to.
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def _workspace(self, slug: str, user):
        return Workspace.objects.filter(
            slug=slug,
            workspace_member__member=user,
            workspace_member__is_active=True,
        ).first()

    def _can_read(self, page: Page, user) -> bool:
        if page.access == 0:
            return True
        project_ids = ProjectPage.objects.filter(page=page).values_list(
            "project_id", flat=True
        )
        return ProjectMember.objects.filter(
            member=user, project_id__in=project_ids, is_active=True
        ).exists()

    def get(self, request, slug: str, page_id: str | None = None):
        workspace = self._workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "not a workspace member"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if page_id is None:
            pages = Page.objects.filter(
                workspace=workspace,
                archived_at__isnull=True,
            ).order_by("-updated_at")
            rows = [
                {
                    "id": str(page.id),
                    "name": page.name,
                    "updated_at": page.updated_at.isoformat(),
                }
                for page in pages
                if self._can_read(page, request.user)
            ]
            return Response({"pages": rows})
        page = Page.objects.filter(
            id=page_id, workspace=workspace, archived_at__isnull=True
        ).first()
        if page is None:
            return Response(
                {"error": "page not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if not self._can_read(page, request.user):
            return Response(
                {"error": "no access to this page"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {
                "id": str(page.id),
                "name": page.name,
                "description_html": page.description_html,
                "description_stripped": page.description_stripped,
                "updated_at": page.updated_at.isoformat(),
                "project_ids": [
                    str(pid)
                    for pid in ProjectPage.objects.filter(page=page).values_list(
                        "project_id", flat=True
                    )
                ],
            }
        )
