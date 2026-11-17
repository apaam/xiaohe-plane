"""Patch Plane's authentication URLconf during image build."""

from pathlib import Path

path = Path("/code/plane/authentication/urls.py")
source = path.read_text(encoding="utf-8")

if "asset_inline_patch" not in source:
    source = (
        "import plane.authentication.views.asset_inline_patch  # xiaohe page image patch\n"
        + source
    )

if "urls_xiaohe" not in source:
    if "from django.urls import include, path" not in source:
        source = source.replace(
            "from django.urls import path",
            "from django.urls import include, path",
        )
    marker = source.rfind("]")
    if marker == -1:
        raise SystemExit("urlpatterns closing bracket not found")
    source = (
        source[:marker]
        + '    path("", include("plane.authentication.urls_xiaohe")),\n'
        + source[marker:]
    )

path.write_text(source, encoding="utf-8")
print("patched plane.authentication.urls")
