#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/screen_park_golf_service}"

cd "$PROJECT_DIR"
docker compose up -d
