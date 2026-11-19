#!/usr/bin/env bash
# Build Plane backend/web images on the build host (ts-linux-ws) and push them
# to the Gitea container registry. The VPS only pulls.
#
#   ./scripts/build-and-push.sh v1.5.0-xh19            # both images
#   COMPONENTS=web ./scripts/build-and-push.sh v1.5.0-xh19
#
# Push goes through the tailnet address (100.64.0.4:3000) so it bypasses the
# nginx rate limit on gitea.xiaohe.team; pull on the VPS uses the public HTTPS
# name. Registry paths are identical, so the pushed manifest is what the VPS
# resolves.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:?usage: build-and-push.sh <tag>  e.g. v1.5.0-xh19}"
REGISTRY="${REGISTRY:-100.64.0.4:3000}"
PULL_REGISTRY="${PULL_REGISTRY:-gitea.xiaohe.team}"
IMAGE_PREFIX="${IMAGE_PREFIX:-lzhshou}"
COMPONENTS="${COMPONENTS:-backend web}"
DOCKER="${DOCKER:-docker}"

# The web bundle, /version.json and the api's X-Build-Id header all carry this
# value, so an operator can tell from one curl which build a client is talking
# to. The deploy compose file pins the same value for the api container.
export XIAOHE_BUILD_ID="${XIAOHE_BUILD_ID:-$TAG}"

push_one() {   # $1 = component, $2 = tag
  local image="$REGISTRY/$IMAGE_PREFIX/xiaohe-plane-$1:$2"
  case "$1" in
    backend) (cd "$REPO_ROOT/auth/plane" && IMAGE_TAG="$image" DOCKER="$DOCKER" bash ./build.sh) ;;
    web)     IMAGE_TAG="$image" DOCKER="$DOCKER" bash "$REPO_ROOT/web/build.sh" ;;
    *)       echo "unknown component: $1" >&2; exit 2 ;;
  esac
  "$DOCKER" push "$image"
  echo "ready: $PULL_REGISTRY/$IMAGE_PREFIX/xiaohe-plane-$1:$2"
}

for c in $COMPONENTS; do
  push_one "$c" "$TAG"
done
