#!/usr/bin/env bash
set -euo pipefail

# Build the Plane web image with xiaohe UI cleanups applied.
# The upstream tree is cloned separately and never vendored into this repo.
#
#   ./web/build.sh                 # build locally
#   DOCKER="sudo docker" ./web/build.sh
#   IMAGE_TAG=... UPSTREAM_REF=v1.5.0 ./web/build.sh

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM_REPO="${UPSTREAM_REPO:-https://github.com/makeplane/plane.git}"
UPSTREAM_REF="${UPSTREAM_REF:-v1.5.0}"
SRC_DIR="${SRC_DIR:-$HOME/plane-web-src}"
IMAGE_TAG="${IMAGE_TAG:-xiaohe-plane-web:${UPSTREAM_REF}-xh1}"
DOCKER="${DOCKER:-docker}"

if [ ! -d "$SRC_DIR/.git" ]; then
  git clone --depth 1 --branch "$UPSTREAM_REF" "$UPSTREAM_REPO" "$SRC_DIR"
fi

cd "$SRC_DIR"
git fetch --depth 1 origin tag "$UPSTREAM_REF" 2>/dev/null || true
git checkout -f "tags/$UPSTREAM_REF"
git clean -fdx

for patch in "$REPO_ROOT"/web/patches/*.patch; do
  echo "applying $(basename "$patch")"
  git apply "$patch"
done

# Build identity. It is compiled into the bundle (0017's version banner compares
# the running bundle against the live server) and served as /version.json, so a
# tab left open across a deploy can notice the new build without a hard refresh.
BUILD_ID="${XIAOHE_BUILD_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)}"
GIT_SHA="$(git rev-parse HEAD)"
BUILT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'export const XIAOHE_BUILD_ID = "%s";\n' "$BUILD_ID" > apps/web/xiaohe-build.ts
mkdir -p "$REPO_ROOT/web/build-version"
printf '{"build_id":"%s","git_sha":"%s","built_at":"%s"}\n' \
  "$BUILD_ID" "$GIT_SHA" "$BUILT_AT" > "$REPO_ROOT/web/build-version/version.json"
echo "build id: $BUILD_ID"

# Fonts are binary assets, so they live here and are copied over instead of
# being carried in a git patch. 0015 imports them for CJK PDF export.
FONT_DIR="apps/web/app/assets/fonts/noto-sans-sc"
mkdir -p "$FONT_DIR"
cp "$REPO_ROOT"/web/assets/fonts/noto-sans-sc/*.ttf "$FONT_DIR"/

# BuildKit not installed: the Dockerfile's pnpm cache mounts are optional.
# Strip them so the legacy builder can run the same file.
if ! $DOCKER buildx version >/dev/null 2>&1; then
  echo "buildx missing, stripping BuildKit cache mounts"
  sed -i 's#^RUN --mount=type=cache,id=pnpm-store,target=/pnpm/store #RUN #' apps/web/Dockerfile.web
fi

BUILD_IMAGE="${BUILD_IMAGE:-xiaohe-plane-web-build:${UPSTREAM_REF}}"

# Only build the frontend installer stage. The upstream image already ships
# Caddy; rebuilding it pulls Go modules through proxy.golang.org, which is
# unreliable here. Runtime assets are copied into the stock web image instead.
$DOCKER build -f apps/web/Dockerfile.web --target installer -t "$BUILD_IMAGE" .

$DOCKER build -f "$REPO_ROOT/web/Dockerfile.runtime" \
  --build-arg "UPSTREAM_IMAGE=makeplane/plane-frontend:${UPSTREAM_REF}" \
  --build-arg "BUILD_IMAGE=${BUILD_IMAGE}" \
  -t "$IMAGE_TAG" "$REPO_ROOT/web"

echo "built $IMAGE_TAG"

# The build image only exists to hand its compiled assets to Dockerfile.runtime
# via COPY --from. Drop it now that the runtime image is built, so repeated
# builds do not pile up dead tags on this shared daemon.
$DOCKER rmi "$BUILD_IMAGE"
