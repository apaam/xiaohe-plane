"""Backfill Plane Profiles and onboarding state.

Run inside the api container after a restore or after creating users outside
the normal auth adapter:

    python manage.py shell < deploy/ensure_profiles.py

Every SSO user gets a Profile on login; this command covers users created by
older versions or by ad-hoc scripts, and avoids the /users/me/profile/ 404
that puts the web app into its maintenance screen.
"""

from __future__ import annotations

from plane.db.models import Profile, User, Workspace


def has_workspace(user: User) -> bool:
    return Workspace.objects.filter(
        workspace_member__member=user,
        workspace_member__is_active=True,
    ).exists()


created = 0
onboarded = 0
for user in User.objects.iterator():
    profile, was_created = Profile.objects.get_or_create(user=user)
    if was_created:
        created += 1
    if not profile.is_onboarded and has_workspace(user):
        profile.is_onboarded = True
        profile.save(update_fields=["is_onboarded"])
        onboarded += 1

print(f"profiles created: {created}; marked onboarded: {onboarded}")
