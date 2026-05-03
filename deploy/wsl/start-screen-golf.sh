#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/user/app/screen_park_golf_web_service}"
DOCKER_WAIT_SECONDS="${DOCKER_WAIT_SECONDS:-60}"
SERVICE_WAIT_SECONDS="${SERVICE_WAIT_SECONDS:-180}"
WEB_URL="${WEB_URL:-http://localhost:8080/}"
DB_SERVICE="${DB_SERVICE:-db}"
DB_CONTAINER="${DB_CONTAINER:-screen-golf-db}"
DB_DATA_DIR="${DB_DATA_DIR:-/var/lib/postgresql/data}"
RECOVERY_LOG="${RECOVERY_LOG:-${PROJECT_DIR}/backups/recovery.log}"

cd "$PROJECT_DIR"

log_recovery() {
    mkdir -p "$(dirname "$RECOVERY_LOG")"
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$*" >> "$RECOVERY_LOG"
}

log_recovery_file_tail() {
    local log_file="$1"

    if [[ ! -s "$log_file" ]]; then
        return 0
    fi

    while IFS= read -r line; do
        log_recovery "compose stderr: ${line}"
    done < <(tail -n 80 "$log_file")
}

is_recoverable_layer_error() {
    local text="${1,,}"

    [[ "$text" == *"rwlayer"* || "$text" == *"snapshot not found"* || "$text" == *"unexpectedly nil"* ]]
}

get_db_state_error() {
    docker inspect -f '{{.State.Error}}' "$DB_CONTAINER" 2>/dev/null || true
}

db_container_uses_named_data_volume() {
    local mount_info
    local mount_type
    local volume_name

    mount_info="$(
        docker inspect \
            -f "{{range .Mounts}}{{if eq .Destination \"${DB_DATA_DIR}\"}}{{.Type}} {{.Name}}{{end}}{{end}}" \
            "$DB_CONTAINER" 2>/dev/null || true
    )"
    read -r mount_type volume_name <<< "$mount_info"

    if [[ "$mount_type" != "volume" || -z "${volume_name:-}" ]]; then
        log_recovery "aborted: ${DB_CONTAINER} does not expose a named volume at ${DB_DATA_DIR}."
        return 1
    fi

    log_recovery "verified: ${DB_CONTAINER} uses named volume ${volume_name} at ${DB_DATA_DIR}."
    return 0
}

detect_db_layer_error() {
    local compose_error_log="$1"
    local state_error

    if [[ -s "$compose_error_log" ]] && is_recoverable_layer_error "$(cat "$compose_error_log")"; then
        return 0
    fi

    state_error="$(get_db_state_error)"
    if [[ -n "$state_error" ]] && is_recoverable_layer_error "$state_error"; then
        log_recovery "inspect state error: ${state_error}"
        return 0
    fi

    return 1
}

remove_db_container_only() {
    if docker compose rm -f "$DB_SERVICE" >> "$RECOVERY_LOG" 2>&1; then
        log_recovery "action: docker compose rm -f ${DB_SERVICE} completed."
    else
        log_recovery "warning: docker compose rm -f ${DB_SERVICE} failed; trying docker rm -f ${DB_CONTAINER}."
    fi

    if docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
        if docker rm -f "$DB_CONTAINER" >> "$RECOVERY_LOG" 2>&1; then
            log_recovery "action: docker rm -f ${DB_CONTAINER} completed."
        else
            log_recovery "failed: docker rm -f ${DB_CONTAINER}."
            echo "Failed to remove ${DB_CONTAINER}; see ${RECOVERY_LOG}." >&2
            return 1
        fi
    fi
}

recover_db_layer_and_start() {
    local compose_error_log="$1"

    if ! detect_db_layer_error "$compose_error_log"; then
        return 1
    fi

    log_recovery "detected: recoverable Docker DB container layer error."
    log_recovery_file_tail "$compose_error_log"

    if ! db_container_uses_named_data_volume; then
        echo "Refusing automatic DB container recovery because the Postgres named volume could not be verified." >&2
        return 1
    fi

    echo "Recovering ${DB_CONTAINER} container layer while preserving the Postgres named volume." >&2
    if ! remove_db_container_only; then
        return 1
    fi

    if docker compose up -d "$DB_SERVICE" >> "$RECOVERY_LOG" 2>&1; then
        log_recovery "action: docker compose up -d ${DB_SERVICE} completed."
    else
        log_recovery "failed: docker compose up -d ${DB_SERVICE}."
        echo "Failed to recreate ${DB_CONTAINER}; see ${RECOVERY_LOG}." >&2
        return 1
    fi

    if docker compose up -d >> "$RECOVERY_LOG" 2>&1; then
        log_recovery "action: docker compose up -d completed after DB container recovery."
        return 0
    fi

    log_recovery "failed: docker compose up -d after DB container recovery."
    echo "Failed to start all services after ${DB_CONTAINER} recovery; see ${RECOVERY_LOG}." >&2
    return 1
}

compose_up_with_db_layer_recovery() {
    local compose_error_log
    local compose_status

    compose_error_log="$(mktemp)"
    if docker compose up -d 2> "$compose_error_log"; then
        rm -f "$compose_error_log"
        return 0
    fi

    compose_status=$?
    cat "$compose_error_log" >&2

    if recover_db_layer_and_start "$compose_error_log"; then
        rm -f "$compose_error_log"
        return 0
    fi

    rm -f "$compose_error_log"
    return "$compose_status"
}

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
compose_up_with_db_layer_recovery
wait_for_container_health "screen-golf-db"
wait_for_container_health "screen-golf-backend"
wait_for_container_health "screen-golf-frontend"
wait_for_container_health "screen-golf-nginx"
wait_for_http
