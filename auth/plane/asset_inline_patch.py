"""Serve Plane page images inline.

Plane's ProjectAssetEndpoint always signs downloads with
Content-Disposition: attachment, so an <img> in a Page cannot render the
asset and shows "Error loading image". This patch keeps the stock permission
checks and only changes the redirect for uploaded PAGE_DESCRIPTION images.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect

from plane.app.views.asset.v2 import ProjectAssetEndpoint
from plane.db.models import FileAsset
from plane.settings.storage import S3Storage

_ORIGINAL_GET = ProjectAssetEndpoint.get

_IMAGE_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}


def _inline_page_image_get(self, request, slug, project_id, pk):
    response = _ORIGINAL_GET(self, request, slug=slug, project_id=project_id, pk=pk)
    if getattr(response, "status_code", None) != 302:
        return response

    asset = FileAsset.objects.filter(
        workspace__slug=slug, project_id=project_id, pk=pk
    ).first()
    if (
        asset is None
        or not asset.is_uploaded
        or asset.entity_type != FileAsset.EntityTypeContext.PAGE_DESCRIPTION
    ):
        return response

    content_type = asset.attributes.get("type")
    if content_type not in _IMAGE_TYPES:
        return response

    storage = S3Storage(request=request)
    signed_url = storage.generate_presigned_url(
        object_name=asset.asset.name,
        disposition="inline",
        filename=asset.attributes.get("name"),
        content_type=content_type,
    )
    return HttpResponseRedirect(signed_url)


ProjectAssetEndpoint.get = _inline_page_image_get
