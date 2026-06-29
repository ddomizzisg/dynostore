#!/bin/bash
set -e

MODE="${1:-apptainer}"

if [[ "$MODE" == "docker" || "$MODE" == "--docker" ]]; then
  echo "Generating admin using Docker..."
  CONTAINER_ID=$(docker ps -q -f name=db_auth | head -n 1)
  if [ -z "$CONTAINER_ID" ]; then
    echo "Error: db_auth container is not running."
    exit 1
  fi
  docker exec "$CONTAINER_ID" python3 /configure/create_admin.py
else
  echo "Generating admin using Apptainer..."
  apptainer exec \
    --env POSTGRES_DB=auth \
    --env POSTGRES_USER=muyalmanager \
    --env POSTGRES_PASSWORD=niCi7unamltrubrlJusp \
    --env ADMIN_USER=dynoadmin \
    --env ADMIN_PASSWORD=XeN5raSsdJkcOMN \
    --env ADMIN_EMAIL=admin@admin \
    --env DB_PORT=5434 \
    instance://db_auth \
    python3 /configure/create_admin.py
fi