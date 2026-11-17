from django.urls import path

from plane.authentication.views.xiaohe_sso import xiaohe_callback, xiaohe_start

urlpatterns = [
    path("xiaohe/start/", xiaohe_start, name="xiaohe-sso-start"),
    path("xiaohe/callback/", xiaohe_callback, name="xiaohe-sso-callback"),
]
