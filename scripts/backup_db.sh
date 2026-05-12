#!/usr/bin/env bash
# Daily backup of DPMBG database to local + (optional) cloud storage.
# Usage: ./scripts/backup_db.sh [output_dir]
# Cron: 0 2 * * * /root/projects/dpmbg/scripts/backup_db.sh

set -euo pipefail

# Config — edit BACKUP_DIR for your env
BACKUP_DIR="${1:-/backups/dpmbg}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DATABASE_URL="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL" ]]; then
  # Try to load from .env relative to script
  ENV_FILE="$(dirname "$0")/../.env"
  if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
  fi
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "[backup] DATABASE_URL not set — aborting" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d-%H%M)
OUT="$BACKUP_DIR/dpmbg-$TS.sql.gz"

echo "[backup] dumping to $OUT"
pg_dump "$DATABASE_URL" | gzip > "$OUT"
echo "[backup] size: $(du -h "$OUT" | cut -f1)"

# Cleanup old backups
echo "[backup] removing backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name "dpmbg-*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Optional: upload to cloud (uncomment + configure rclone first)
# rclone copy "$OUT" drive:dpmbg-backups/ --progress

echo "[backup] done"
