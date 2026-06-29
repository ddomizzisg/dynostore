#!/bin/bash
TOKEN=$1
MODE="${2:-apptainer}"

if [ -z "$TOKEN" ]; then
    echo "Usage: $0 <admin_token> [mode (apptainer|docker)]"
    exit 1
fi

echo "Registering 10 Data Containers with Metadata Server..."
if [[ "$MODE" == "docker" || "$MODE" == "--docker" ]]; then
  echo "Using Docker..."

  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.19
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.20
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.21
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.22
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.23
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.24
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.25
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.26
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.27
  docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" 10.88.0.28

else
  echo "Using Apptainer..."
  for i in {1..10}; do
    PORT=$((20000 + i))
    echo "Registering datacontainer$i at http://localhost:$PORT/"
    apptainer exec \
      -B $(pwd)/datacontainer/code:/app \
      --pwd /app \
      --env APIGATEWAY_HOST=localhost:8070 \
      sif_images/dynostore_datacontainer_v1.sif \
      python3 regist_on_metadata.py "$TOKEN" "http://localhost:$PORT/"
  done
fi
echo "All Data Containers registered successfully!"
