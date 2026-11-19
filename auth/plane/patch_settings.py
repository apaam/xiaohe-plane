# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

"""Patch Plane's settings during image build.

Adds the xiaohe throttles to DRF's default throttle classes and installs the
read-cache middleware. Both edits are idempotent and fail the build loudly if
the upstream text has moved, rather than shipping an image that silently lost
its guard.
"""

import os
from pathlib import Path

path = Path(os.environ.get("XIAOHE_SETTINGS_PATH", "/code/plane/settings/common.py"))
source = path.read_text(encoding="utf-8")

THROTTLE_MARKER = "plane.authentication.xiaohe_throttle.XiaoheUserThrottle"
if THROTTLE_MARKER not in source:
    original = (
        '"DEFAULT_THROTTLE_CLASSES": '
        '("rest_framework.throttling.AnonRateThrottle",),'
    )
    replacement = (
        '"DEFAULT_THROTTLE_CLASSES": (\n'
        '        "rest_framework.throttling.AnonRateThrottle",\n'
        '        "plane.authentication.xiaohe_throttle.XiaoheUserThrottle",\n'
        '        "plane.authentication.xiaohe_throttle.XiaoheBotThrottle",\n'
        "    ),"
    )
    if original not in source:
        raise SystemExit("DEFAULT_THROTTLE_CLASSES not found or already reshaped")
    source = source.replace(original, replacement, 1)

MIDDLEWARE_MARKER = "plane.middleware.xiaohe_guard.XiaoheGuardMiddleware"
if MIDDLEWARE_MARKER not in source:
    anchor = '    "plane.middleware.logger.RequestLoggerMiddleware",\n]'
    if anchor not in source:
        raise SystemExit("MIDDLEWARE tail not found or already reshaped")
    source = source.replace(
        anchor,
        "    \"plane.middleware.logger.RequestLoggerMiddleware\",\n"
        f'    "{MIDDLEWARE_MARKER}",\n]',
        1,
    )

path.write_text(source, encoding="utf-8")
print("patched plane.settings.common (throttles + read guard)")
