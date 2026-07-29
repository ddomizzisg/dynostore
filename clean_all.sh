#!/bin/bash

# Script to clean the system: data, logs, and file metadata
# Auth information and server registrations are kept.

COMPOSE_FILE="docker-compose.dev.yml"

echo "Cleaning data in data containers..."
for i in {1..10}; do
    docker compose -f $COMPOSE_FILE exec -T datacontainer$i sh -c 'rm -rf /data/objects/*' 2>/dev/null
done

echo "Cleaning cache in api gateway..."
docker compose -f $COMPOSE_FILE exec -T apigateway sh -c 'rm -rf /app/.cache/*' 2>/dev/null
docker compose -f $COMPOSE_FILE exec -T apigateway sh -c 'rm -rf /app/.temp/*' 2>/dev/null

echo "Cleaning log files..."
docker compose -f $COMPOSE_FILE exec -T auth sh -c 'rm -rf /var/www/html/log/*' 2>/dev/null
docker compose -f $COMPOSE_FILE exec -T apigateway sh -c 'rm -rf /app/logs/*' 2>/dev/null
# datacontainer code is mounted to all datacontainers, we can clean it from one
docker compose -f $COMPOSE_FILE exec -T datacontainer1 sh -c 'rm -rf /app/logs/*' 2>/dev/null
docker compose -f $COMPOSE_FILE exec -T pub_sub sh -c 'rm -rf /var/www/html/log/*' 2>/dev/null
rm -rf logs/* 2>/dev/null
docker compose -f $COMPOSE_FILE exec -T metadata_server sh -c 'rm -f /var/www/metadata.log' 2>/dev/null

echo "Cleaning metadata assigned to files in database..."
# The metadata database container is named db_metadata
# We truncate the files table which will cascade to chunks, files_in_servers, and abekeys.
# Server utilization is calculated dynamically, so it will drop to zero.
if docker ps | grep -q db_metadata; then
    docker compose -f $COMPOSE_FILE exec -T db_metadata psql -U metadata -d metadata-api -c "TRUNCATE TABLE files, chunks, files_in_servers, abekeys CASCADE;"
    echo "Metadata cleaned successfully."
else
    echo "WARNING: db_metadata container is not running."
    echo "Please start the containers (e.g., docker compose -f $COMPOSE_FILE up -d db_metadata) and run this script again to clear the database metadata."
fi

echo "System cleanup complete. Auth info and servers are preserved."
