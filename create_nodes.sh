#!/bin/bash
TOKEN=$1

if [ -z "$TOKEN" ]; then
    echo "Usage: $0 <admin_token>"
    exit 1
fi

echo "Registering 10 Data Containers with Metadata Server..."
for i in {1..10}; do
  PORT=$((20000 + i))
  echo "Registering datacontainer$i at http://localhost:$PORT/"
  apptainer exec \
    -B $(pwd)/datacontainer/code:/app \
    --pwd /app \
    --env APIGATEWAY_HOST=localhost:8070 \
    sif_images/dynostore_datacontainer_v1.sif \
    python3 regist_on_metadata.py $TOKEN http://localhost:$PORT/
done
echo "All Data Containers registered successfully!"
