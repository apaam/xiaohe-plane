# SPDX-License-Identifier: AGPL-3.0-only
# xiaohe modification; see SOURCE.md and LICENSE.

from django.urls import path

from plane.authentication.views.bots import BotActionView, BotsView
from plane.authentication.views.xiaohe_sso import (
    xiaohe_callback,
    xiaohe_logout,
    xiaohe_start,
)

urlpatterns = [
    path("xiaohe/start/", xiaohe_start, name="xiaohe-sso-start"),
    path("xiaohe/callback/", xiaohe_callback, name="xiaohe-sso-callback"),
    path("xiaohe/logout/", xiaohe_logout, name="xiaohe-sso-logout"),
    path("xiaohe/bots/<str:slug>/", BotsView.as_view(), name="xiaohe-bots"),
    path(
        "xiaohe/bots/<str:slug>/<uuid:bot_id>/<str:action>/",
        BotActionView.as_view(),
        name="xiaohe-bot-action",
    ),
]
