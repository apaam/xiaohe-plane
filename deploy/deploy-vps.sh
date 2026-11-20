#!/usr/bin/env bash
# Deploy a prebuilt Plane tag to the VPS with digest pinning and rollback.
#
#   ./deploy/deploy-vps.sh v1.5.0-xh24
#
# Images are built and pushed elsewhere (scripts/build-and-push.sh on
# ts-linux-ws). This script pulls the tag, resolves its digest, writes a
# release override that pins the digest, snapshots the compose files, starts
# the stack, gates on /version.json plus running services, and rolls back to
# the previous release snapshot when the gate fails.
#
# No blue-green: Plane is a twelve-container stack and a second copy does not
# fit the host. Digest-pinned releases + a previous snapshot give the same
# rollback guarantee without doubling memory.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${XIAOHE_PLANE_SSH:-ts-xiaohe}"
REMOTE_DIR="${XIAOHE_PLANE_DIR:-plane-selfhost}"
TAG="${1:-}"
[[ -n "$TAG" ]] || {
  echo "usage: deploy-vps.sh <tag>   e.g. v1.5.0-xh24" >&2
  exit 2
}
RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
BACKEND="gitea.xiaohe.team/lzhshou/xiaohe-plane-backend:$TAG"
WEB="gitea.xiaohe.team/lzhshou/xiaohe-plane-web:$TAG"

echo "==> deploy Plane $TAG (release $RELEASE_ID) → $REMOTE:$REMOTE_DIR"
ssh "$REMOTE" \
  "TAG=$(printf '%q' "$TAG") RELEASE_ID=$(printf '%q' "$RELEASE_ID") REMOTE_DIR=$(printf '%q' "$REMOTE_DIR") BACKEND=$(printf '%q' "$BACKEND") WEB=$(printf '%q' "$WEB") bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"
RELEASES="$PWD/releases"
RELEASE="$RELEASES/$RELEASE_ID"
PREV="$(readlink -f "$RELEASES/current" 2>/dev/null || true)"
BASE=(sudo docker compose --env-file plane.env -f docker-compose.yaml -f docker-compose.override.yml)

mkdir -p "$RELEASE"
cp docker-compose.yaml docker-compose.override.yml plane.env "$RELEASE/"

echo "==> pull $TAG"
sudo docker pull "$BACKEND"
sudo docker pull "$WEB"
digest() {
  sudo docker inspect --format \
    '{{if .RepoDigests}}{{index .RepoDigests 0}}{{else}}{{.Id}}{{end}}' "$1"
}
BACKEND_ID="$(digest "$BACKEND")"
WEB_ID="$(digest "$WEB")"
printf 'services:\n  api:\n    image: "%s"\n  web:\n    image: "%s"\n' \
  "$BACKEND_ID" "$WEB_ID" > "$RELEASE/docker-compose.release.yml"
REL=(sudo docker compose --env-file plane.env -f docker-compose.yaml \
  -f docker-compose.override.yml -f "$RELEASE/docker-compose.release.yml")

echo "==> validate compose"
"${REL[@]}" config >/dev/null

echo "==> pre-deploy backup"
bash backup-plane.sh || echo "!! backup failed; continuing (check ~/plane-backups)" >&2

BIND="$(grep -E '^PLANE_BIND_IP=' plane.env | tail -1 | cut -d= -f2- || true)"
BIND="${BIND:-127.0.0.1}"

services_running() {
  local expected running
  # migrator is a one-shot service: it exits after applying migrations.
  expected="$("${REL[@]}" config --services | grep -vx migrator | sort)"
  running="$(sudo docker compose --env-file plane.env -f docker-compose.yaml \
    -f docker-compose.override.yml -f "$RELEASE/docker-compose.release.yml" \
    ps --status running --services 2>/dev/null | sort)"
  [[ "$expected" == "$running" ]]
}

web_build_id() {
  curl -fsS --max-time 3 "http://${BIND}:8080/version.json" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("build_id", ""))' \
      2>/dev/null || true
}

health() {   # $1 = expected build id, empty means any
  local want="${1:-}" i current
  for ((i = 0; i < 180; i++)); do
    if services_running; then
      current="$(web_build_id)"
      if [[ -n "$current" ]] && { [[ -z "$want" ]] || [[ "$current" == "$want" ]]; }; then
        return 0
      fi
    fi
    sleep 1
  done
  return 1
}

echo "==> start release $TAG"
"${REL[@]}" up -d
if health "$TAG"; then
  :
else
  echo "!! health gate FAILED for $TAG" >&2
  if [[ -n "$PREV" && -f "$PREV/docker-compose.release.yml" ]]; then
    echo "==> rolling back to $(basename "$PREV")" >&2
    OLD=(sudo docker compose --env-file plane.env -f docker-compose.yaml \
      -f docker-compose.override.yml -f "$PREV/docker-compose.release.yml")
    "${OLD[@]}" up -d
    if health ""; then
      echo "==> rolled back to $(basename "$PREV") (healthy)" >&2
    else
      echo "!! rollback ALSO unhealthy — manual intervention required" >&2
    fi
  else
    echo "==> first release: restarting the tagged compose as-is" >&2
    "${BASE[@]}" up -d
  fi
  exit 1
fi

sudo ln -sfn "$RELEASE" "$RELEASES/current"
printf '{"service":"xiaohe-plane","tag":"%s","backend":"%s","web":"%s","deployed_at":"%s","previous":"%s","status":"ok"}\n' \
  "$TAG" "$BACKEND_ID" "$WEB_ID" "$RELEASE_ID" "$(basename "${PREV:-none}")" \
  > "$RELEASE/manifest.json"
echo "==> healthy: $TAG (build_id $(web_build_id))"

# Keep current + four previous releases.
CURRENT="$(readlink -f "$RELEASES/current")"
kept=0
while IFS= read -r dir; do
  dir="${dir%/}"
  [[ "$dir" == "$CURRENT" ]] && continue
  kept=$((kept + 1))
  if [[ "$kept" -gt 4 ]]; then
    echo "==> prune $(basename "$dir")"
    rm -rf "$dir"
  fi
done < <(ls -1dt "$RELEASES"/*/ 2>/dev/null || true)
REMOTE

echo "==> smoke https://plane.xiaohe.team/version.json"
curl -fsS --max-time 15 https://plane.xiaohe.team/version.json | head -c 400
echo
echo "==> done (Plane $TAG)"
