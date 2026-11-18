# Source code and license

This repository is the source location for the self-hosted Plane instance at
`https://plane.xiaohe.team`.

- Upstream: [makeplane/plane](https://github.com/makeplane/plane), Community Edition **v1.5.0**
- License: **AGPL-3.0-only**, see [LICENSE](LICENSE)
- This repository contains xiaohe's modifications, deployment configuration and
  rebuild instructions. Upstream source is not vendored; the pinned upstream tag
  plus the patches below reconstruct the running version.

## Modified components

- `auth/plane/`: xiaohe accounts SSO adapter, page-image inline patch and the
  backend image Dockerfile.
- `web/patches/`: frontend patches (cleanup of upstream promo, edition badge,
  auth footer, quickstart guide; CJK fonts for PDF export).
- `web/assets/fonts/`: Noto Sans SC subset bundled for CJK PDF export.
- `deploy/`: Docker Compose override, nginx, backup and provisioning scripts.

## Reconstruct the source

```bash
git clone --depth 1 --branch v1.5.0 https://github.com/makeplane/plane.git plane-src
cd plane-src
for p in /path/to/xiaohe-plane/web/patches/*.patch; do git apply "$p"; done
# Backend adapter: copy the files referenced by auth/plane/Dockerfile
# into the image build context, or build from auth/plane/ directly.
```

The frontend image is built by `web/build.sh`; the backend image by
`auth/plane/build.sh`. Both pin upstream `v1.5.0`.

## Network source offer

Users interacting with this service over a network may obtain the corresponding
source from this public repository at no charge:

<https://gitea.xiaohe.team/apaam/xiaohe-plane>

If that host is unreachable, open an issue or contact the operator; a source
archive will be provided.
