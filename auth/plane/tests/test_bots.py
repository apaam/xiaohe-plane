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

from plane.authentication.views.bots import BotActionView, _bot_payload
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

    def _act(self, action: str, data=None):
        request = self.factory.post("/", data or {}, format="json")
        force_authenticate(request, user=self.admin)
        view = BotActionView.as_view()
        return view(
            request,
            slug=self.workspace.slug,
            bot_id=str(self.bot.id),
            action=action,
        )


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
