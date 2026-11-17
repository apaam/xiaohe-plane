"""Create/update an invite-only Plane user and add it to the workspace/project.

Run inside the api container, e.g.:

    PLANE_USER_EMAIL=student@example.com \
    PLANE_USER_PASSWORD='...' \
    PLANE_PROJECT_ID=6e74852f-... \
    python manage.py shell < /tmp/create_user.py

Environment:
    PLANE_USER_EMAIL      required
    PLANE_USER_NAME       optional display name
    PLANE_USER_PASSWORD   optional; generated and printed once if omitted
    PLANE_WORKSPACE_SLUG  default research
    PLANE_PROJECT_ID      optional; add to this project
    PLANE_WORKSPACE_ROLE  default 15 (Member)
    PLANE_PROJECT_ROLE    default 15 (Member)
"""

from __future__ import annotations

import os
import secrets
import string

from plane.db.models import Profile, Project, ProjectMember, User, Workspace, WorkspaceMember


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(20))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
            and any(char in "!@#$%^&*" for char in password)
        ):
            return password


email = os.environ["PLANE_USER_EMAIL"].strip().lower()
name = os.environ.get("PLANE_USER_NAME", email.split("@")[0]).strip()
password = os.environ.get("PLANE_USER_PASSWORD") or generate_password()
generated = "PLANE_USER_PASSWORD" not in os.environ

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
        "is_password_autoset": False,
        "user_timezone": os.environ.get("PLANE_USER_TIMEZONE", "Asia/Shanghai"),
    },
)
user.is_active = True
user.is_email_verified = True
user.user_timezone = os.environ.get("PLANE_USER_TIMEZONE", "Asia/Shanghai")
user.set_password(password)
user.save()

workspace = Workspace.objects.get(slug=os.environ.get("PLANE_WORKSPACE_SLUG", "research"))
WorkspaceMember.objects.get_or_create(
    workspace=workspace,
    member=user,
    defaults={"role": int(os.environ.get("PLANE_WORKSPACE_ROLE", "15"))},
)
profile, _ = Profile.objects.get_or_create(user=user)
profile.is_onboarded = True
profile.last_workspace_id = workspace.id
profile.save(update_fields=["is_onboarded", "last_workspace_id"])

project_id = os.environ.get("PLANE_PROJECT_ID")
if project_id:
    project = Project.objects.get(id=project_id)
    ProjectMember.objects.get_or_create(
        project=project,
        member=user,
        defaults={"role": int(os.environ.get("PLANE_PROJECT_ROLE", "15"))},
    )

print("user", "created" if created else "updated", email)
if generated:
    print("generated_password", password)
