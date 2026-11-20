#!/usr/bin/env bash
# Flip Plane to a previous release snapshot and health-check it.
#
#   ./deploy/rollback-vps.sh                  # newest release other than current
#   ./deploy/rollback-vps.sh 20261120T013204Z # explicit release id
#
# The snapshot pins both images by digest. A failed health check restores the
# release that was live before this command.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="${XIAOHE_PLANE_SSH:-ts-xiaohe}"
REMOTE_DIR="${XIAOHE_PLANE_DIR:-plane-selfhost}"
WANT="${1:-}"

ssh "$REMOTE" "WANT=$(printf '%q' "$WANT") REMOTE_DIR=$(printf '%q' "$REMOTE_DIR") bash -s" <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"
RELEASES="$PWD/releases"
CURRENT="$(readlink -f "$RELEASES/current" 2>/dev/null || true)"
[[ -d "$CURRENT" ]] || CURRENT=""
if [[ -n "$WANT" ]]; then
  TARGET="$RELEASES/$WANT"
else
  while IFS= read -r dir; do
    dir="${dir%/}"
    if [[ "$dir" != "$CURRENT" && -f "$dir/docker-compose.release.yml" ]]; then
      TARGET="$dir"
      break
    fi
  done < <(ls -1dt "$RELEASES"/*/ 2>/dev/null || true)
fi
if [[ -z "${TARGET:-}" || ! -f "$TARGET/docker-compose.release.yml" ]]; then
  echo "no rollback target found (current=${CURRENT:-none} want=${WANT:-newest-other})" >&2
  exit 1
fi

BIND="$(grep -E '^PLANE_BIND_IP=' plane.env | tail -1 | cut -d= -f2- || true)"
BIND="${BIND:-127.0.0.1}"
REL=(sudo docker compose --env-file plane.env -f docker-compose.yaml \
  -f docker-compose.override.yml -f "$TARGET/docker-compose.release.yml")

health() {
  local i build
  for ((i = 0; i < 180; i++)); do
    build="$(curl -fsS --max-time 3 "http://${BIND}:8080/version.json" 2>/dev/null \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("build_id",""))' \
        2>/dev/null || true)"
    if [[ -n "$build" ]] && \
       [[ "$("${REL[@]}" config --services | grep -vx migrator | sort)" == \
          "$(sudo docker compose --env-file plane.env -f docker-compose.yaml \
             -f docker-compose.override.yml -f "$TARGET/docker-compose.release.yml" \
             ps --status running --services 2>/dev/null | sort)" ]]; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "==> flip ${CURRENT:+$(basename "$CURRENT")} → $(basename "$TARGET")"
"${REL[@]}" up -d </dev/null
if health; then
  sudo ln -sfn "$TARGET" "$RELEASES/current"
  echo "==> rolled back to $(basename "$TARGET") (healthy)"
  curl -sS --max-time 5 "http://${BIND}:8080/version.json" || true
  echo
  exit 0
fi
echo "!! target release is unhealthy" >&2
if [[ -n "$CURRENT" ]]; then
  echo "==> restoring $(basename "$CURRENT")" >&2
  OLD=(sudo docker compose --env-file plane.env -f docker-compose.yaml \
    -f docker-compose.override.yml -f "$CURRENT/docker-compose.release.yml")
  "${OLD[@]}" up -d </dev/null
  TARGET="$CURRENT"
  if health; then
    echo "==> restored $(basename "$CURRENT") (healthy)" >&2
  else
    echo "!! original release ALSO unhealthy — manual intervention required" >&2
  fi
fi
exit 1
REMOTE
