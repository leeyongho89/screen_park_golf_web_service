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

get_compose_container_names() {
    docker compose ps -a --format '{{.Name}}'
}

get_compose_service_for_container() {
    local container_name="$1"
    local name
    local service

    while read -r name service; do
        if [[ "$name" == "$container_name" ]]; then
            printf '%s\n' "$service"
            return 0
        fi
    done < <(docker compose ps -a --format '{{.Name}} {{.Service}}')
}

is_compose_container() {
    local container_name="$1"
    local name

    while read -r name; do
        if [[ "$name" == "$container_name" ]]; then
            return 0
        fi
    done < <(get_compose_container_names)

    return 1
}

print_recoverable_container_from_id() {
    local container_id="$1"
    local container_name

    container_name="$(docker inspect -f '{{.Name}}' "$container_id" 2>/dev/null || true)"
    container_name="${container_name#/}"

    if [[ -n "$container_name" ]] && is_compose_container "$container_name"; then
        printf '%s\n' "$container_name"
    fi
}

get_recoverable_layer_containers() {
    local compose_error_log="$1"
    local container_id
    local container_name
    local state_error

    {
        if [[ -s "$compose_error_log" ]] && is_recoverable_layer_error "$(cat "$compose_error_log")"; then
            while read -r container_id; do
                print_recoverable_container_from_id "$container_id"
            done < <(grep -Eo 'container [0-9a-f]{12,64}' "$compose_error_log" | awk '{print $2}' | sort -u)
        fi

        while read -r container_name; do
            state_error="$(docker inspect -f '{{.State.Error}}' "$container_name" 2>/dev/null || true)"
            if [[ -n "$state_error" ]] && is_recoverable_layer_error "$state_error"; then
                log_recovery "inspect state error for ${container_name}: ${state_error}"
                printf '%s\n' "$container_name"
            fi
        done < <(get_compose_container_names)
    } | sort -u
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

container_has_named_volume() {
    local container_name="$1"

    [[ -n "$(docker inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{println .Name}}{{end}}{{end}}' "$container_name" 2>/dev/null || true)" ]]
}

container_can_be_recreated() {
    local service="$1"
    local container_name="$2"

    if [[ "$service" == "$DB_SERVICE" || "$container_name" == "$DB_CONTAINER" ]]; then
        db_container_uses_named_data_volume
        return 0
    fi

    if ! container_has_named_volume "$container_name"; then
        return 0
    fi

    log_recovery "aborted: ${container_name} has a named Docker volume and is not configured for automatic recovery."
    echo "Refusing automatic recovery for ${container_name} because it has a named Docker volume." >&2
    return 1
}

remove_compose_container_only() {
    local service="$1"
    local container_name="$2"

    if docker compose rm -f "$service" >> "$RECOVERY_LOG" 2>&1; then
        log_recovery "action: docker compose rm -f ${service} completed."
    else
        log_recovery "warning: docker compose rm -f ${service} failed; trying docker rm -f ${container_name}."
    fi

    if docker inspect "$container_name" >/dev/null 2>&1; then
        if docker rm -f "$container_name" >> "$RECOVERY_LOG" 2>&1; then
            log_recovery "action: docker rm -f ${container_name} completed."
        else
            log_recovery "failed: docker rm -f ${container_name}."
            echo "Failed to remove ${container_name}; see ${RECOVERY_LOG}." >&2
            return 1
        fi
    fi
}

recover_layer_and_start() {
    local compose_error_log="$1"
    local containers=()
    local container_name
    local service

    mapfile -t containers < <(get_recoverable_layer_containers "$compose_error_log")
    if (( ${#containers[@]} == 0 )); then
        return 1
    fi

    log_recovery "detected: recoverable Docker container layer error."
    log_recovery_file_tail "$compose_error_log"

    for container_name in "${containers[@]}"; do
        service="$(get_compose_service_for_container "$container_name")"
        if [[ -z "$service" ]]; then
            log_recovery "aborted: could not resolve compose service for ${container_name}."
            echo "Refusing automatic recovery because the Compose service for ${container_name} could not be resolved." >&2
            return 1
        fi

        if ! container_can_be_recreated "$service" "$container_name"; then
            return 1
        fi

        echo "Recovering ${container_name} container layer for service ${service}." >&2
        log_recovery "recovering: ${container_name} (${service})."
        if ! remove_compose_container_only "$service" "$container_name"; then
            return 1
        fi
    done

    if docker compose up -d >> "$RECOVERY_LOG" 2>&1; then
        log_recovery "action: docker compose up -d completed after container layer recovery."
        return 0
    fi

    log_recovery "failed: docker compose up -d after container layer recovery."
    echo "Failed to start all services after container layer recovery; see ${RECOVERY_LOG}." >&2
    return 1
}

compose_up_with_layer_recovery() {
    local compose_error_log
    local compose_status

    compose_error_log="$(mktemp)"
    if docker compose up -d 2> "$compose_error_log"; then
        rm -f "$compose_error_log"
        return 0
    fi

    compose_status=$?
    cat "$compose_error_log" >&2

    if recover_layer_and_start "$compose_error_log"; then
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
compose_up_with_layer_recovery
wait_for_container_health "screen-golf-db"
wait_for_container_health "screen-golf-backend"
wait_for_container_health "screen-golf-frontend"
wait_for_container_health "screen-golf-nginx"
wait_for_http
