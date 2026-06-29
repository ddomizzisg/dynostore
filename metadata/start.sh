#!/bin/sh

################################################################################
# Start the uvicorn service and the log watcher
################################################################################

# Start the log watcher in the background 
#logwatcher  2>&1 | tee /kagio/logs/metadata.log &
# Start the uvicorn server for the metadata service
uvicorn main:app --reload --host 0.0.0.0 --port 80 2>&1 | tee metadata.log