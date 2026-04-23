#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/user/app/screen_park_golf_web_service}"
DOCKER_WAIT_SECONDS="${DOCKER_WAIT_SECONDS:-60}"
SERVICE_WAIT_SECONDS="${SERVICE_WAIT_SECONDS:-180}"
WEB_URL="${WEB_URL:-http://localhost:8080/}"

cd "$PROJECT_DIR"

wait_for_docker() {
    local waited=0
    until docker info >/dev/null 2>&1; do
        if (( waited >= DOCKER_WAIT_SECONDS )); then
            echo "Docker daemon did not become ready within ${DOCKER_WAIT_SECONDS}s." >&2
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
}

wait_for_container_health() {
    local container_name="$1"
    local waited=0
    local state
    local health

    while true; do
        state="$(docker inspect -f '{{.State.Status}}' "$container_name" 2>/dev/null || true)"
        health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null || true)"

        if [[ "$state" == "running" && ( "$health" == "healthy" || "$health" == "none" ) ]]; then
            return 0
        fi

        if [[ "$state" == "exited" || "$state" == "dead" ]]; then
            echo "${container_name} is in unexpected state: ${state}." >&2
            docker logs --tail 100 "$container_name" >&2 || true
            return 1
        fi

        if (( waited >= SERVICE_WAIT_SECONDS )); then
            echo "Timed out waiting for ${container_name} to become ready." >&2
            docker ps -a >&2 || true
            return 1
        fi

        sleep 2
        waited=$((waited + 2))
    done
}

wait_for_http() {
    local waited=0
    until curl -fsS "$WEB_URL" >/dev/null 2>&1; do
        if (( waited >= SERVICE_WAIT_SECONDS )); then
            echo "Timed out waiting for ${WEB_URL} to respond." >&2
            return 1
        fi
        sleep 2
        waited=$((waited + 2))
    done
}

wait_for_docker
docker compose up -d
wait_for_container_health "screen-golf-db"
wait_for_container_health "screen-golf-backend"
wait_for_container_health "screen-golf-frontend"
wait_for_container_health "screen-golf-nginx"
wait_for_http
