#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
IMAGE_TAG="${IMAGE_TAG:-xiaohe-plane-backend:v1.5.0-xh13}"
docker build -t "$IMAGE_TAG" .
echo "built $IMAGE_TAG"
