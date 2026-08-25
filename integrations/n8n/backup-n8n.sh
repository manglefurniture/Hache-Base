#!/usr/bin/env bash
set -Eeuo pipefail

: "${N8N_CONTAINER:?N8N_CONTAINER is required}"
: "${N8N_BACKUP_ROOT:?N8N_BACKUP_ROOT is required}"
N8N_DATA_PATH="${N8N_DATA_PATH:-/home/node/.n8n}"

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }

stamp="$(date -u +%Y%m%d-%H%M%S)"
destination="${N8N_BACKUP_ROOT%/}/n8n-${stamp}"
mkdir -p "$destination"
chmod 700 "$destination"

was_running="$(docker inspect -f '{{.State.Running}}' "$N8N_CONTAINER")"
restart_container() {
  if [[ "$was_running" == "true" ]]; then
    docker start "$N8N_CONTAINER" >/dev/null || true
  fi
}
trap restart_container EXIT

# Stopping the container avoids copying a changing SQLite database/WAL.
if [[ "$was_running" == "true" ]]; then
  docker stop "$N8N_CONTAINER" >/dev/null
fi

docker inspect "$N8N_CONTAINER" > "$destination/container-inspect.json"
docker cp "$N8N_CONTAINER:$N8N_DATA_PATH" "$destination/data"

if [[ -f "$destination/data/database.sqlite" ]]; then
  sha256sum "$destination/data/database.sqlite" > "$destination/SHA256SUMS"
fi

echo "$destination"
echo "N8N_BACKUP_OK"
