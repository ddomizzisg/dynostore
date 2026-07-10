#!/bin/bash
TOKEN=$1
MODE="${2:-apptainer}"

if [ -z "$TOKEN" ]; then
    echo "Usage: $0 <admin_token> [mode (apptainer|docker)]"
    exit 1
fi

# Define capacities in bytes
# Low: 1GB memory, 10GB storage
MEM_LOW=$((1 * 1024 * 1024 * 1024))
STO_LOW=$((10 * 1024 * 1024 * 1024))

# Medium: 2GB memory, 50GB storage
MEM_MED=$((2 * 1024 * 1024 * 1024))
STO_MED=$((50 * 1024 * 1024 * 1024))

# High: 4GB memory, 100GB storage
MEM_HIGH=$((4 * 1024 * 1024 * 1024))
STO_HIGH=$((100 * 1024 * 1024 * 1024))

get_capacity() {
    local idx=$1
    local class=$((idx % 3))
    if [ $class -eq 1 ]; then
        echo "$MEM_LOW $STO_LOW"
    elif [ $class -eq 2 ]; then
        echo "$MEM_MED $STO_MED"
    else
        echo "$MEM_HIGH $STO_HIGH"
    fi
}

echo "Registering 10 Data Containers with Metadata Server..."
if [[ "$MODE" == "docker" || "$MODE" == "--docker" ]]; then
  echo "Using Docker..."
  for i in {1..10}; do
    read -r MEM STO <<< $(get_capacity $i)
    IP="10.88.0.$((18 + i))"
    echo "Registering Docker datacontainer at $IP with Mem: $MEM, Storage: $STO"
    docker compose -f docker-compose.dev.yml exec datacontainer1 python3 regist_on_metadata.py "$TOKEN" "$IP" -m "$MEM" -s "$STO"
  done
else
  echo "Using Apptainer..."
  for i in {1..10}; do
    read -r MEM STO <<< $(get_capacity $i)
    PORT=$((20000 + i))
    echo "Registering Apptainer datacontainer$i at http://localhost:$PORT/ with Mem: $MEM, Storage: $STO"
    apptainer exec \
      -B $(pwd)/datacontainer/code:/app \
      --pwd /app \
      --env APIGATEWAY_HOST=localhost:8070 \
      sif_images/dynostore_datacontainer_v1.sif \
      python3 regist_on_metadata.py "$TOKEN" "http://localhost:$PORT/" -m "$MEM" -s "$STO"
  done
fi
echo "All Data Containers registered successfully!"
