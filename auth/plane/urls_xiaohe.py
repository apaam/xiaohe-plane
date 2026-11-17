# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

from django.urls import path

from plane.authentication.views.xiaohe_sso import (
    xiaohe_callback,
    xiaohe_logout,
    xiaohe_start,
)

urlpatterns = [
    path("xiaohe/start/", xiaohe_start, name="xiaohe-sso-start"),
    path("xiaohe/callback/", xiaohe_callback, name="xiaohe-sso-callback"),
    path("xiaohe/logout/", xiaohe_logout, name="xiaohe-sso-logout"),
]
