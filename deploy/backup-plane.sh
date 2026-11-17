#!/usr/bin/env bash
set -euo pipefail

HOME_DIR="${HOME}/plane-selfhost"
OUT="${HOME}/plane-backups"
TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
chmod 700 "$OUT"

cd "$HOME_DIR"
set -a
. ./plane.env
set +a

sudo -n docker compose --env-file plane.env \
    -f docker-compose.yaml -f docker-compose.override.yml \
    exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" plane-db \
    pg_dump -U plane plane > "$OUT/plane-db-$TS.sql"

sudo -n docker run --rm \
    -v plane-selfhost_uploads:/data \
    -v "$OUT":/backup \
    alpine:3.20 tar czf "/backup/uploads-$TS.tar.gz" -C /data .

chmod 600 "$OUT"/plane-db-*.sql 2>/dev/null || true
sudo -n chown "$(id -u):$(id -g)" "$OUT"/uploads-*.tar.gz 2>/dev/null || true
sudo -n chmod 600 "$OUT"/uploads-*.tar.gz 2>/dev/null || true
find "$OUT" -type f -name 'plane-db-*.sql' -mtime +14 -delete
find "$OUT" -type f -name 'uploads-*.tar.gz' -mtime +14 -delete

echo "backup: $OUT/plane-db-$TS.sql $OUT/uploads-$TS.tar.gz"
