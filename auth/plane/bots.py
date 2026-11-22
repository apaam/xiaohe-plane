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

import base64
import logging
import re
from datetime import date
from uuid import UUID

from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from plane.api.middleware.api_authentication import APIKeyAuthentication
from plane.authentication.bot_guard import bot_owner_id, set_bot_owner
from plane.authentication.session import BaseSessionAuthentication
from plane.authentication.xiaohe_throttle import XiaoheBotThrottle, XiaoheUserThrottle
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
from plane.utils.content_validator import validate_binary_data, validate_html_content

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
        ProjectMember.objects.filter(
            member=bot, project__workspace=workspace, is_active=True
        )
        .select_related("project")
        .values("project_id", "project__identifier", "project__name")
    )
    tokens = APIToken.objects.filter(user=bot, workspace=workspace)
    owner_id = bot_owner_id(bot.id)
    owner = User.objects.filter(id=owner_id).first() if owner_id else None
    last_used = max(
        (token.last_used for token in tokens if token.last_used), default=None
    )
    return {
        "id": str(bot.id),
        "email": bot.email,
        "display_name": bot.display_name,
        "owner": (
            {
                "id": str(owner.id),
                "display_name": owner.display_name,
                "email": owner.email,
            }
            if owner
            else None
        ),
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
        owner_id = str(request.data.get("owner_id") or request.user.id)
        if not WorkspaceMember.objects.filter(
            workspace=workspace, member_id=owner_id, is_active=True
        ).exists():
            return Response(
                {"error": "owner must be an active workspace member"},
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
            description=f"created from the workspace bots page; owner={owner_id}",
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
            owner_id = bot_owner_id(bot.id)
            tokens.update(is_active=False)
            token = APIToken.objects.create(
                user=bot,
                workspace=workspace,
                user_type=1,
                label=f"{bot.display_name} bot token",
                description=(
                    f"rotated from the workspace bots page; owner={owner_id}"
                    if owner_id
                    else "rotated from the workspace bots page"
                ),
            )
            logger.info(
                "xiaohe bot rotated email=%s by=%s", bot.email, request.user.email
            )
            return Response({"token": token.token})
        if action == "owner":
            # A bot always has an owner: clearing it is not supported, use
            # disable instead. Validate the id here so a bad value comes back
            # as 400 rather than a ValidationError raised by the UUID filter.
            owner_id = str(request.data.get("owner_id") or "").strip()
            if not owner_id:
                return Response(
                    {"error": "owner_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                owner_uuid = UUID(owner_id)
            except ValueError:
                return Response(
                    {"error": "owner_id must be a valid UUID"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not WorkspaceMember.objects.filter(
                workspace=workspace, member_id=owner_uuid, is_active=True
            ).exists():
                return Response(
                    {"error": f"owner {owner_id} is not an active workspace member"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            owner_id = str(owner_uuid)
            set_bot_owner(bot, owner_id)
            logger.info(
                "xiaohe bot owner set email=%s owner=%s by=%s",
                bot.email,
                owner_id,
                request.user.email,
            )
            return Response({"ok": True, "owner_id": owner_id})
        if action == "disable":
            # Only the bot's credentials (tokens) and its workspace
            # membership are revoked. Project memberships are left as they
            # are so that a project admin's explicit removal of the bot from
            # a project survives a disable -> enable round trip.
            tokens.update(is_active=False)
            if member:
                member.is_active = False
                member.save(update_fields=["is_active"])
            bot.is_active = False
            bot.save(update_fields=["is_active"])
            logger.info(
                "xiaohe bot disabled email=%s by=%s", bot.email, request.user.email
            )
            return Response({"ok": True})
        if action == "enable":
            # Mirror of disable: restore the workspace membership and the
            # user flag, nothing else. Project memberships are not touched:
            # re-adding the bot to a project is an explicit project-settings
            # action. Tokens stay revoked as well; rotate to issue a new one.
            #
            # Historical rows: builds up to xh16 set ProjectMember.is_active
            # to false on disable. Those rows are NOT restored here on
            # purpose, since the same flag also records deliberate removals.
            # Re-add the bot from the project's member settings if needed.
            if member:
                member.is_active = True
                member.save(update_fields=["is_active"])
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
    """Read/write Pages access for bot tokens.

    The official v1 API (and the web app API) do not expose Pages to API-key
    callers. This endpoint fills that gap for pages linked to projects the
    caller belongs to, and for workspace pages when the caller is a workspace
    member. Writes follow the web editor's semantics: HTML-only updates clear
    the JSON/binary body, and the stripped text is recomputed by Page.save().
    """

    authentication_classes = [APIKeyAuthentication, BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [XiaoheUserThrottle, XiaoheBotThrottle]

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

    def _can_write_project(self, user, project_ids) -> bool:
        if not project_ids:
            return True
        try:
            member_ids = {
                str(pid)
                for pid in ProjectMember.objects.filter(
                    member=user, project_id__in=project_ids, is_active=True
                ).values_list("project_id", flat=True)
            }
        except Exception:
            return False
        return {str(pid) for pid in project_ids} <= member_ids

    def _can_write_any_project(self, user, project_ids) -> bool:
        if not project_ids:
            return True
        try:
            return ProjectMember.objects.filter(
                member=user, project_id__in=project_ids, is_active=True
            ).exists()
        except Exception:
            return False

    def _can_write_page(self, page: Page, user) -> bool:
        project_ids = list(
            ProjectPage.objects.filter(page=page).values_list("project_id", flat=True)
        )
        if page.access == 0:
            # Public pages are shared with the whole workspace; treat them as
            # read-only except for the owner (matches how Plane surfaces them).
            return page.owned_by_id == user.id
        if project_ids:
            # Match the web app: a member of any linked project may edit the
            # page. Creating a new page or moving it still requires membership
            # in every target project via _can_write_project.
            return self._can_write_any_project(user, project_ids)
        return WorkspaceMember.objects.filter(
            workspace=page.workspace, member=user, is_active=True
        ).exists()

    def _page_payload(self, page: Page) -> dict:
        return {
            "id": str(page.id),
            "name": page.name,
            "description_html": page.description_html,
            "description_stripped": page.description_stripped,
            "description_json": page.description_json,
            "access": page.access,
            "color": page.color,
            "parent_id": str(page.parent_id) if page.parent_id else None,
            "archived_at": page.archived_at.isoformat() if page.archived_at else None,
            "updated_at": page.updated_at.isoformat(),
            "project_ids": [
                str(pid)
                for pid in ProjectPage.objects.filter(page=page).values_list(
                    "project_id", flat=True
                )
            ],
        }

    def _clean_html(self, value):
        if value is None:
            value = ""
        ok, error, clean = validate_html_content(value)
        if not ok:
            return None, error
        return (clean if clean is not None else ""), None

    def _decode_binary(self, value):
        if value in (None, ""):
            return None, None
        if isinstance(value, str):
            try:
                data = base64.b64decode(value, validate=True)
            except Exception:
                return None, "description_binary is not valid base64"
        elif isinstance(value, (bytes, bytearray)):
            data = bytes(value)
        else:
            return None, "description_binary must be a base64 string"
        ok, error = validate_binary_data(data)
        if not ok:
            return None, error
        return data, None

    def _project_ids(self, workspace, requested):
        if requested is None:
            requested = []
        if not isinstance(requested, list):
            return None, "project_ids must be a list"
        requested = [str(pid) for pid in requested]
        if not requested:
            return [], None
        try:
            projects = list(
                Project.objects.filter(id__in=requested, workspace=workspace)
            )
        except Exception:
            return None, "invalid project_ids"
        if len(projects) != len(set(requested)):
            return None, "invalid project_ids"
        return requested, None

    def _validate_access(self, value):
        try:
            access = int(value)
        except (TypeError, ValueError):
            return None
        return access if access in (0, 1) else None

    def _parent(self, workspace, value, page_id=None):
        if value in (None, ""):
            return None, None
        try:
            qs = Page.objects.filter(
                id=value, workspace=workspace, archived_at__isnull=True
            )
            if page_id:
                qs = qs.exclude(id=page_id)
            parent = qs.first()
        except Exception:
            parent = None
        if parent is None:
            return None, "parent page not found"
        return parent, None

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
        return Response(self._page_payload(page))

    def post(self, request, slug: str):
        workspace = self._workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "not a workspace member"},
                status=status.HTTP_403_FORBIDDEN,
            )
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        project_ids, error = self._project_ids(
            workspace, request.data.get("project_ids")
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        if not self._can_write_project(request.user, project_ids):
            return Response(
                {"error": "no access to one of the projects"},
                status=status.HTTP_403_FORBIDDEN,
            )
        html, error = self._clean_html(
            request.data.get("description_html", "<p></p>")
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        binary, error = self._decode_binary(request.data.get("description_binary"))
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        description_json = request.data.get("description_json", {})
        if description_json is None:
            description_json = {}
        if not isinstance(description_json, dict):
            return Response(
                {"error": "description_json must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        access = self._validate_access(
            request.data.get("access", 1 if project_ids else 0)
        )
        if access is None:
            return Response(
                {"error": "access must be 0 or 1"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parent, error = self._parent(
            workspace, request.data.get("parent_id") or request.data.get("parent")
        )
        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)
        page = Page.objects.create(
            workspace=workspace,
            name=name,
            description_html=html,
            description_json=description_json,
            description_binary=binary,
            owned_by=request.user,
            access=access,
            color=request.data.get("color", ""),
            parent=parent,
        )
        page.created_by = request.user
        page.updated_by = request.user
        page.save(disable_auto_set_user=True)
        for project_id in project_ids:
            link = ProjectPage.objects.create(
                project_id=project_id, page=page, workspace=workspace
            )
            link.created_by = request.user
            link.updated_by = request.user
            link.save(disable_auto_set_user=True)
        return Response(
            self._page_payload(page), status=status.HTTP_201_CREATED
        )

    def patch(self, request, slug: str, page_id: str):
        workspace = self._workspace(slug, request.user)
        if workspace is None:
            return Response(
                {"error": "not a workspace member"},
                status=status.HTTP_403_FORBIDDEN,
            )
        page = Page.objects.filter(
            id=page_id, workspace=workspace, archived_at__isnull=True
        ).first()
        if page is None:
            return Response(
                {"error": "page not found"}, status=status.HTTP_404_NOT_FOUND
            )
        if not self._can_write_page(page, request.user):
            return Response(
                {"error": "no access to this page"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data

        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                return Response(
                    {"error": "name is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            page.name = name

        if "description_html" in data:
            html, error = self._clean_html(data.get("description_html"))
            if error:
                return Response(
                    {"error": error}, status=status.HTTP_400_BAD_REQUEST
                )
            page.description_html = html
            if "description_json" in data:
                description_json = data.get("description_json")
                if description_json is None:
                    description_json = {}
                if not isinstance(description_json, dict):
                    return Response(
                        {"error": "description_json must be an object"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                page.description_json = description_json
            else:
                # HTML-only writes clear the JSON/binary body, matching the
                # web editor and the 2026-11-19 validation record.
                page.description_json = {}
            if "description_binary" in data:
                binary, error = self._decode_binary(data.get("description_binary"))
                if error:
                    return Response(
                        {"error": error}, status=status.HTTP_400_BAD_REQUEST
                    )
                page.description_binary = binary
            else:
                page.description_binary = None
        else:
            if "description_json" in data:
                description_json = data.get("description_json")
                if description_json is None:
                    description_json = {}
                if not isinstance(description_json, dict):
                    return Response(
                        {"error": "description_json must be an object"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                page.description_json = description_json
            if "description_binary" in data:
                binary, error = self._decode_binary(data.get("description_binary"))
                if error:
                    return Response(
                        {"error": error}, status=status.HTTP_400_BAD_REQUEST
                    )
                page.description_binary = binary

        if "access" in data:
            access = self._validate_access(data.get("access"))
            if access is None:
                return Response(
                    {"error": "access must be 0 or 1"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if page.access != access and page.owned_by_id != request.user.id:
                return Response(
                    {"error": "access can only be changed by the page owner"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            page.access = access
        if "color" in data:
            page.color = str(data.get("color") or "")
        if "is_locked" in data:
            page.is_locked = bool(data.get("is_locked"))
        if "parent_id" in data or "parent" in data:
            parent, error = self._parent(
                workspace,
                data.get("parent_id") if "parent_id" in data else data.get("parent"),
                page_id=page.id,
            )
            if error:
                return Response(
                    {"error": error}, status=status.HTTP_400_BAD_REQUEST
                )
            page.parent = parent
        if "archive" in data:
            page.archived_at = date.today() if data.get("archive") else None
        elif "archived_at" in data:
            value = data.get("archived_at")
            if value in (None, ""):
                page.archived_at = None
            else:
                parsed = (
                    value
                    if isinstance(value, date)
                    else parse_date(str(value))
                )
                if parsed is None:
                    return Response(
                        {"error": "archived_at must be YYYY-MM-DD"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                page.archived_at = parsed

        if "project_ids" in data:
            project_ids, error = self._project_ids(workspace, data.get("project_ids"))
            if error:
                return Response(
                    {"error": error}, status=status.HTTP_400_BAD_REQUEST
                )
            if not self._can_write_project(request.user, project_ids):
                return Response(
                    {"error": "no access to one of the projects"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            ProjectPage.objects.filter(page=page).delete()
            for project_id in project_ids:
                link = ProjectPage.objects.create(
                    project_id=project_id, page=page, workspace=workspace
                )
                link.created_by = request.user
                link.updated_by = request.user
                link.save(disable_auto_set_user=True)

        page.updated_by = request.user
        page.save(disable_auto_set_user=True)
        return Response(self._page_payload(page))


class BotsAssignableView(APIView):
    """Which bots the current user may assign (for greying out the rest)."""

    authentication_classes = [BaseSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str):
        workspace = Workspace.objects.filter(
            slug=slug,
            workspace_member__member=request.user,
            workspace_member__is_active=True,
        ).first()
        if workspace is None:
            return Response(
                {"error": "not a workspace member"},
                status=status.HTTP_403_FORBIDDEN,
            )
        member = WorkspaceMember.objects.filter(
            workspace=workspace, member=request.user, is_active=True
        ).first()
        is_admin = bool(member and member.role >= ADMIN_ROLE)
        rows = []
        for bot in _bot_queryset(workspace):
            owner_id = bot_owner_id(bot.id)
            rows.append(
                {
                    "id": str(bot.id),
                    "display_name": bot.display_name,
                    "can_assign": is_admin or (owner_id is not None and str(owner_id) == str(request.user.id)),
                }
            )
        return Response({"bots": rows})
