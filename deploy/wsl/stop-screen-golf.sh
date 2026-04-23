#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/user/app/screen_park_golf_web_service}"

cd "$PROJECT_DIR"
docker compose down
