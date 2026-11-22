"""Create or update a member's Plane bot user and issue it an API token.

Env:
    PLANE_BOT_EMAIL       bot account email (required)
    PLANE_BOT_NAME        display name (default: email prefix)
    PLANE_BOT_OWNER_ID    optional owner user UUID recorded on the token
    PLANE_PROJECT_IDS     optional comma-separated project UUIDs
    PLANE_WORKSPACE_SLUG  default research
    PLANE_BOT_WORKSPACE_ROLE  default 15 (Member)
    PLANE_BOT_PROJECT_ROLE    default 15 (Member)

Run inside the api container:

    PLANE_BOT_EMAIL=zhangsan-bot@xiaohe.local \
    PLANE_BOT_NAME='Zhangsan Bot' \
    PLANE_PROJECT_IDS=<uuid>[,<uuid>...] \
    python manage.py shell < /tmp/create_bot.py

The token is printed once; hand it to the member over a private channel.
Do not put it in Plane issues, chat groups or the repository.

Why is_bot=False: Plane hides bot users from project member/assignee lists.
Keeping the account as a normal user (with a Bot display name and a Bot API
token) lets members pick it in the UI while keeping its identity separate.
"""

from __future__ import annotations

import os

from plane.db.models import APIToken, Profile, Project, ProjectMember, User, Workspace, WorkspaceMember


email = os.environ["PLANE_BOT_EMAIL"].strip().lower()
name = os.environ.get("PLANE_BOT_NAME", email.split("@")[0]).strip()
workspace_slug = os.environ.get("PLANE_WORKSPACE_SLUG", "research")
workspace_role = int(os.environ.get("PLANE_BOT_WORKSPACE_ROLE", "15"))
project_role = int(os.environ.get("PLANE_BOT_PROJECT_ROLE", "15"))
project_ids = [p.strip() for p in os.environ.get("PLANE_PROJECT_IDS", "").split(",") if p.strip()]

first_name, _, last_name = name.partition(" ")
username = email.replace("@", "-").replace(".", "-")[:30]

user, created = User.objects.get_or_create(
    email=email,
    defaults={
        "username": username,
        "display_name": name,
        "first_name": first_name,
        "last_name": last_name,
        "is_active": True,
        "is_email_verified": True,
        "is_password_autoset": True,
        # Plane filters is_bot=True out of member/assignee selectors.
        "is_bot": False,
    },
)
user.is_active = True
user.is_email_verified = True
user.is_bot = False
user.display_name = name
user.set_unusable_password()
user.save()

workspace = Workspace.objects.get(slug=workspace_slug)
WorkspaceMember.objects.get_or_create(
    workspace=workspace,
    member=user,
    defaults={"role": workspace_role},
)
profile, _ = Profile.objects.get_or_create(user=user)
profile.is_onboarded = True
profile.last_workspace_id = workspace.id
profile.save(update_fields=["is_onboarded", "last_workspace_id"])

projects = list(Project.objects.filter(id__in=project_ids)) if project_ids else []
for project in projects:
    ProjectMember.objects.get_or_create(
        project=project,
        member=user,
        defaults={"role": project_role},
    )

owner_id = os.environ.get("PLANE_BOT_OWNER_ID", "").strip()
description = "Provisioned by deploy/create_bot.py"
if owner_id:
    description += f"; owner={owner_id}"
token = APIToken.objects.create(
    user=user,
    workspace=workspace,
    user_type=1,
    label=f"{name} bot token",
    description=description,
)

print("bot", "created" if created else "updated", email)
print("workspace", workspace.slug)
print("projects", [f"{p.identifier}:{p.name}" for p in projects] or "none")
print("token", token.token)
