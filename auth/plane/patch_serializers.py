# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Insert the bot ownership guard into Plane's issue serializers."""

from pathlib import Path

TARGETS = (
    "/code/plane/app/serializers/issue.py",
    "/code/plane/api/serializers/issue.py",
)

CREATE_ANCHOR = '        default_assignee_id = self.context["default_assignee_id"]\n'
CREATE_GUARD = (
    "        # xiaohe bot ownership guard\n"
    "        from plane.authentication.bot_guard import ensure_assignees_allowed\n"
    "        ensure_assignees_allowed(\n"
    "            self.context.get(\"request\"), workspace_id, assignees, default_assignee_id\n"
    "        )\n"
)

UPDATE_ANCHOR = "        updated_by_id = instance.updated_by_id\n"
UPDATE_GUARD = (
    "        # xiaohe bot ownership guard\n"
    "        from plane.authentication.bot_guard import ensure_assignees_allowed\n"
    "        ensure_assignees_allowed(\n"
    "            self.context.get(\"request\"), workspace_id, assignees\n"
    "        )\n"
)

VIEW_TARGET = "/code/plane/api/views/issue.py"
if Path(VIEW_TARGET).is_file():
    view = Path(VIEW_TARGET)
    text = view.read_text(encoding="utf-8")
    if '"request": request' not in text:
        import re as _re

        text = _re.sub(
            r'context=\{\n(\s*)"project_id": project_id,',
            lambda m: (
                'context={\n'
                + m.group(1)
                + '"request": request,\n'
                + m.group(1)
                + '"project_id": project_id,'
            ),
            text,
        )
        text = text.replace(
            'context={"project_id": project_id, "workspace_id": project.workspace_id},',
            'context={"request": request, "project_id": project_id, '
            '"workspace_id": project.workspace_id},',
        )
        view.write_text(text, encoding="utf-8")
        print(f"added request context to {VIEW_TARGET}")

for target in TARGETS:
    path = Path(target)
    if not path.is_file():
        continue
    source = path.read_text(encoding="utf-8")
    if "xiaohe bot ownership guard" in source:
        continue
    if CREATE_ANCHOR in source:
        source = source.replace(CREATE_ANCHOR, CREATE_ANCHOR + CREATE_GUARD, 1)
    if UPDATE_ANCHOR in source:
        source = source.replace(UPDATE_ANCHOR, UPDATE_ANCHOR + UPDATE_GUARD, 1)
    path.write_text(source, encoding="utf-8")
    print(f"patched bot guard into {target}")
