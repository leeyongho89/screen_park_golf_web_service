#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="${PROJECT_DIR:-/home/user/app/screen_park_golf_web_service}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-30}"

timestamp="$(date +"%Y%m%d_%H%M%S")"
backup_file="$BACKUP_DIR/screen_golf_${timestamp}.dump"
tmp_file="${backup_file}.tmp"

cd "$PROJECT_DIR"
mkdir -p "$BACKUP_DIR"

if ! docker compose exec -T db sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null'; then
    echo "Backup failed: db container is not ready." >&2
    exit 1
fi

if ! docker compose exec -T db sh -lc \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
    > "$tmp_file"; then
    rm -f "$tmp_file"
    echo "Backup failed: pg_dump did not complete." >&2
    exit 1
fi

if [[ ! -s "$tmp_file" ]]; then
    rm -f "$tmp_file"
    echo "Backup failed: dump file was empty." >&2
    exit 1
fi

mv "$tmp_file" "$backup_file"

if [[ "$BACKUP_KEEP_DAYS" =~ ^[0-9]+$ ]] && (( BACKUP_KEEP_DAYS > 0 )); then
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'screen_golf_*.dump' -mtime "+${BACKUP_KEEP_DAYS}" -delete
fi

echo "Backup created: $backup_file"
