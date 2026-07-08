#!/bin/bash

# Script to clean the system: data, logs, and file metadata
# Auth information and server registrations are kept.

echo "Cleaning data in data containers..."
rm -rf datacontainer/objects*/*

echo "Cleaning log files..."
rm -rf auth/auth/log/* 2>/dev/null
rm -rf APIGateway/app/logs/* 2>/dev/null
rm -rf datacontainer/code/logs/* 2>/dev/null
rm -rf pub_sub/pub_sub/log/* 2>/dev/null
rm -rf logs/* 2>/dev/null
rm -f metadata/app/metadata.log 2>/dev/null

echo "Cleaning metadata assigned to files in database..."
# The metadata database container is named db_metadata
# We truncate the files table which will cascade to chunks, files_in_servers, and abekeys.
# Server utilization is calculated dynamically, so it will drop to zero.
if docker ps | grep -q db_metadata; then
    docker compose exec db_metadata psql -U metadata -d metadata-api -c "TRUNCATE TABLE files, chunks, files_in_servers, abekeys CASCADE;"
    echo "Metadata cleaned successfully."
else
    echo "WARNING: db_metadata container is not running."
    echo "Please start the containers (e.g., docker-compose -f docker-compose.dev.yml up -d db_metadata) and run this script again to clear the database metadata."
fi

echo "System cleanup complete. Auth info and servers are preserved."
