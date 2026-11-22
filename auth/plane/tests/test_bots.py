# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Tests for the xiaohe workspace bot endpoints.

The module lives in the Plane backend image as
``plane.authentication.views.bots``; run these tests inside that image
(see ``auth/plane/README.md``):

    cp auth/plane/bots.py /code/plane/authentication/views/bots.py
    cp auth/plane/tests/test_bots.py \
        /code/plane/authentication/views/test_xiaohe_bots.py
    python manage.py test plane.authentication.views.test_xiaohe_bots \
        --settings=plane.settings.test
"""

import uuid

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from plane.authentication.views.bots import (
    BotActionView,
    BotsView,
    _bot_payload,
)
from plane.db.models import (
    APIToken,
    Project,
    ProjectMember,
    User,
    Workspace,
    WorkspaceMember,
)

ADMIN_ROLE = 20
MEMBER_ROLE = 15


class BotTestBase(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = User.objects.create(
            email="admin@example.com",
            username="xh-admin",
            display_name="Admin",
        )
        self.workspace = Workspace.objects.create(
            name="Test Workspace", slug="xh-bot-tests", owner=self.admin
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace, member=self.admin, role=ADMIN_ROLE
        )
        self.bot = User.objects.create(
            email="alpha-bot@xiaohe.local",
            username="alpha-bot",
            display_name="Alpha",
        )
        self.bot_member = WorkspaceMember.objects.create(
            workspace=self.workspace, member=self.bot, role=MEMBER_ROLE
        )
        self.kept = self._project("Kept project", "KEPT")
        self.removed = self._project("Removed project", "GONE")
        self.kept_membership = ProjectMember.objects.create(
            workspace=self.workspace,
            project=self.kept,
            member=self.bot,
            role=MEMBER_ROLE,
        )
        # Simulates a project admin removing the bot from the project.
        self.removed_membership = ProjectMember.objects.create(
            workspace=self.workspace,
            project=self.removed,
            member=self.bot,
            role=MEMBER_ROLE,
            is_active=False,
        )
        self.token = APIToken.objects.create(
            user=self.bot,
            workspace=self.workspace,
            user_type=1,
            label="alpha bot token",
            description=f"owner={self.admin.id}",
        )

    def _project(self, name: str, identifier: str) -> Project:
        return Project.objects.create(
            workspace=self.workspace,
            name=name,
            identifier=identifier,
            created_by=self.admin,
        )

    def _act(self, action: str, data=None, user=None, bot=None):
        request = self.factory.post("/", data or {}, format="json")
        force_authenticate(request, user=user or self.admin)
        view = BotActionView.as_view()
        return view(
            request,
            slug=self.workspace.slug,
            bot_id=str((bot or self.bot).id),
            action=action,
        )

    def _list(self, user):
        request = self.factory.get("/")
        force_authenticate(request, user=user)
        return BotsView.as_view()(request, slug=self.workspace.slug)

    def _member(self, email: str, name: str):
        user = User.objects.create(
            email=email, username=f"xh-{email.split('@')[0]}", display_name=name
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace, member=user, role=MEMBER_ROLE
        )
        return user

    def _bot(self, email: str, name: str, owner_id):
        bot = User.objects.create(
            email=email, username=email.split("@")[0], display_name=name
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace, member=bot, role=MEMBER_ROLE
        )
        APIToken.objects.create(
            user=bot,
            workspace=self.workspace,
            user_type=1,
            label=f"{name} bot token",
            description=f"owner={owner_id}",
        )
        return bot


class BotPayloadTests(BotTestBase):
    def test_payload_lists_only_active_project_memberships(self):
        member = WorkspaceMember.objects.get(pk=self.bot_member.pk)
        payload = _bot_payload(self.bot, self.workspace, member)
        self.assertEqual(
            [row["identifier"] for row in payload["projects"]], ["KEPT"]
        )


class BotOwnerTests(BotTestBase):
    def test_owner_rejects_empty_id(self):
        response = self._act("owner", {"owner_id": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "owner_id is required")

    def test_owner_rejects_missing_id(self):
        response = self._act("owner", {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "owner_id is required")

    def test_owner_rejects_malformed_uuid(self):
        response = self._act("owner", {"owner_id": "not-a-uuid"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "owner_id must be a valid UUID")

    def test_owner_rejects_non_member(self):
        response = self._act("owner", {"owner_id": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not an active workspace member", response.data["error"])

    def test_owner_rejects_inactive_member(self):
        self.bot_member.is_active = False
        self.bot_member.save(update_fields=["is_active"])
        response = self._act("owner", {"owner_id": str(self.bot.id)})
        self.assertEqual(response.status_code, 400)

    def test_owner_sets_active_member(self):
        other = User.objects.create(
            email="other@example.com",
            username="xh-other",
            display_name="Other",
        )
        WorkspaceMember.objects.create(
            workspace=self.workspace, member=other, role=MEMBER_ROLE
        )
        response = self._act("owner", {"owner_id": str(other.id)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["owner_id"], str(other.id))
        self.token.refresh_from_db()
        self.assertIn(f"owner={other.id}", self.token.description)


class BotDisableEnableTests(BotTestBase):
    def test_disable_keeps_project_memberships_untouched(self):
        response = self._act("disable")
        self.assertEqual(response.status_code, 200)
        self.token.refresh_from_db()
        self.assertFalse(self.token.is_active)
        self.bot_member.refresh_from_db()
        self.assertFalse(self.bot_member.is_active)
        self.kept_membership.refresh_from_db()
        self.removed_membership.refresh_from_db()
        self.assertTrue(self.kept_membership.is_active)
        self.assertFalse(self.removed_membership.is_active)

    def test_enable_does_not_resurrect_removed_project_member(self):
        self.assertEqual(self._act("disable").status_code, 200)
        response = self._act("enable")
        self.assertEqual(response.status_code, 200)
        self.bot_member.refresh_from_db()
        self.assertTrue(self.bot_member.is_active)
        self.kept_membership.refresh_from_db()
        self.removed_membership.refresh_from_db()
        self.assertTrue(self.kept_membership.is_active)
        self.assertFalse(self.removed_membership.is_active)

    def test_disabled_bot_payload_keeps_its_project_list(self):
        self.assertEqual(self._act("disable").status_code, 200)
        member = WorkspaceMember.objects.get(pk=self.bot_member.pk)
        payload = _bot_payload(self.bot, self.workspace, member)
        self.assertFalse(payload["is_active"])
        self.assertEqual(
            [row["identifier"] for row in payload["projects"]], ["KEPT"]
        )


class BotListScopeTests(BotTestBase):
    def test_admin_sees_every_bot(self):
        owner = self._member("owner@example.com", "Owner")
        self._bot("beta-bot@xiaohe.local", "Beta", owner.id)
        response = self._list(self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_admin"])
        self.assertEqual(
            sorted(row["display_name"] for row in response.data["bots"]),
            ["Alpha", "Beta"],
        )

    def test_member_sees_only_owned_bots(self):
        owner = self._member("owner@example.com", "Owner")
        beta = self._bot("beta-bot@xiaohe.local", "Beta", owner.id)
        response = self._list(owner)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_admin"])
        self.assertEqual([row["id"] for row in response.data["bots"]], [str(beta.id)])
        self.assertTrue(response.data["bots"][0]["can_rename"])

    def test_member_without_bots_gets_empty_list(self):
        stranger = self._member("stranger@example.com", "Stranger")
        response = self._list(stranger)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bots"], [])

    def test_payload_marks_rename_permission(self):
        member = WorkspaceMember.objects.get(pk=self.bot_member.pk)
        self.assertTrue(
            _bot_payload(self.bot, self.workspace, member, can_rename=True)[
                "can_rename"
            ]
        )
        self.assertFalse(
            _bot_payload(self.bot, self.workspace, member)["can_rename"]
        )


class BotRenameTests(BotTestBase):
    def test_admin_renames_any_bot(self):
        response = self._act("rename", {"name": "LZS bot"})
        self.assertEqual(response.status_code, 200)
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.display_name, "LZS bot")
        self.assertEqual(self.bot.first_name, "LZS")
        self.assertEqual(self.bot.last_name, "bot")
        # The identity (email) is untouched so memberships and tokens survive.
        self.assertEqual(self.bot.email, "alpha-bot@xiaohe.local")
        self.assertTrue(response.data["bot"]["can_rename"])

    def test_owner_renames_own_bot(self):
        owner = self._member("owner@example.com", "Owner")
        self.token.description = f"owner={owner.id}"
        self.token.save(update_fields=["description"])
        response = self._act("rename", {"name": "LZS bot"}, user=owner)
        self.assertEqual(response.status_code, 200)
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.display_name, "LZS bot")

    def test_non_owner_member_cannot_rename(self):
        stranger = self._member("stranger@example.com", "Stranger")
        response = self._act("rename", {"name": "Hijacked"}, user=stranger)
        self.assertEqual(response.status_code, 403)
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.display_name, "Alpha")

    def test_non_owner_member_cannot_rotate(self):
        stranger = self._member("stranger@example.com", "Stranger")
        response = self._act("rotate", user=stranger)
        self.assertEqual(response.status_code, 403)

    def test_rename_rejects_blank_and_overlong_names(self):
        self.assertEqual(self._act("rename", {"name": "   "}).status_code, 400)
        self.assertEqual(
            self._act("rename", {"name": "x" * 65}).status_code, 400
        )
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.display_name, "Alpha")

    def test_rename_collapses_internal_whitespace(self):
        response = self._act("rename", {"name": "  LZS   agent "})
        self.assertEqual(response.status_code, 200)
        self.bot.refresh_from_db()
        self.assertEqual(self.bot.display_name, "LZS agent")
