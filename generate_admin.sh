#!/bin/bash
set -e

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