#!/usr/bin/env bash
set -euo pipefail

ROOT="${HOME}/.xiaohe/plane"
TOKEN_FILE="${ROOT}/agent-token"

if [ ! -f "$TOKEN_FILE" ]; then
    echo "missing Plane token: $TOKEN_FILE" >&2
    exit 1
fi

export PLANE_API_KEY="$(cat "$TOKEN_FILE")"
export PLANE_WORKSPACE_SLUG="${PLANE_WORKSPACE_SLUG:-research}"
export PLANE_BASE_URL="${PLANE_BASE_URL:-https://plane.xiaohe.team}"

UVX="${UVX_BIN:-}"
if [ -z "$UVX" ]; then
    for candidate in "${HOME}/.local/bin/uvx" /opt/homebrew/bin/uvx /usr/local/bin/uvx; do
        if [ -x "$candidate" ]; then
            UVX="$candidate"
            break
        fi
    done
fi

if [ -z "$UVX" ]; then
    echo "uvx not found; install uv first" >&2
    exit 1
fi

exec "$UVX" plane-mcp-server stdio
