#!/bin/bash
echo "DynoStore - Apptainer Deployment Script"
echo "Welcome to the Apptainer deployment script!"

mkdir -p sif_images
cd sif_images

echo "Pulling DynoStore SIF images from Docker Hub..."
if [ -f "dynostore_metadata_v3_1.sif" ] && [ -f "dynostore_apigateway_v1_1.sif" ] && \
    [ -f "mysql_5.7.sif" ] && [ -f "dynostore_auth_v1.sif" ] && \
    [ -f "dynostore_databaseauth_v1.sif" ] && [ -f "dynostore_frontend_v1.sif" ] && \
    [ -f "dynostore_dbpubsub_v1.sif" ] && [ -f "dynostore_pubsub_v1.sif" ] && \
    [ -f "dynostore_datacontainer_v1.sif" ]; then
    echo "All images already exist. Skipping pull."
else
    apptainer pull dynostore_metadata_v3_1.sif docker://dynostore/metadata:v3.1
    apptainer pull dynostore_apigateway_v1_1.sif docker://dynostore/apigateway:v1.1
    apptainer pull mysql_5.7.sif docker://mysql:5.7
    apptainer pull dynostore_auth_v1.sif docker://dynostore/auth:v1
    apptainer pull dynostore_databaseauth_v1.sif docker://dynostore/databaseauth:v1
    apptainer pull dynostore_frontend_v1.sif docker://dynostore/frontend:v1
    apptainer pull dynostore_dbpubsub_v1.sif docker://dynostore/dbpubsub:v1
    apptainer pull dynostore_pubsub_v1.sif docker://dynostore/pubsub:v1
    apptainer pull dynostore_datacontainer_v1.sif docker://dynostore/datacontainer:v1
    echo "All images have been successfully pulled!"
fi

cd ..

echo "Creating necessary directories..."
mkdir -p logs data/db_metadata data/db_auth data/db_pub_sub data/run_postgresql_auth data/run_postgresql_pubsub APIGateway/data apache_configs/auth apache_configs/frontend apache_configs/pub_sub
mkdir -p data/run_apache2_auth data/lock_apache2_auth data/log_apache2_auth
mkdir -p data/run_apache2_pubsub data/lock_apache2_pubsub data/log_apache2_pubsub
mkdir -p data/run_apache2_frontend data/lock_apache2_frontend data/log_apache2_frontend

echo "Cleaning up stale PID files and orphaned processes..."
pkill -f logwatcher || true
pkill -f gunicorn || true
rm -f data/db_auth/postmaster.pid data/db_pub_sub/postmaster.pid
rm -f data/run_apache2_*/apache2.pid
rm -rf data/run_postgresql_*/*
rm -f data/run_postgresql_*/.s.*

# Helper for Apache configs
generate_apache_config() {
  local service=$1
  local port=$2
  echo "Listen $port" > apache_configs/$service/ports.conf
  echo "PidFile /var/run/apache2/apache2.pid" >> apache_configs/$service/ports.conf
  echo "<VirtualHost *:$port>
    DocumentRoot /var/www/html
    ErrorLog \${APACHE_LOG_DIR}/error.log
    CustomLog \${APACHE_LOG_DIR}/access.log combined
</VirtualHost>" > apache_configs/$service/000-default.conf
}

generate_apache_config auth 8090
generate_apache_config frontend 8091
generate_apache_config pub_sub 8093

# Common Kagio env
KAGIO_ENV="--env API_BASE_URL=http://localhost:8080 \
--env ROOT_USER=root \
--env KAGIO_FOXX_URL=http://localhost:8529/_db/_system/kagio \
--env KAGIO_FOXX_DB=fgcs \
--env ENABLE_KAGIO=${ENABLE_KAGIO:-true} \
--env ENABLE_REPLICATOR=${ENABLE_REPLICATOR:-true}"

# 1. Databases
echo "Starting db_metadata..."
rm -f data/db_metadata/mysql.sock data/db_metadata/mysql.sock.lock
apptainer instance start -B $(pwd)/data/db_metadata:/var/lib/mysql sif_images/mysql_5.7.sif db_metadata
apptainer exec $KAGIO_ENV --env MYSQL_DATABASE='metadata-api' --env MYSQL_USER='metadata' --env MYSQL_PASSWORD='metadata2023' --env MYSQL_ROOT_PASSWORD='metadata2023' instance://db_metadata /usr/local/bin/docker-entrypoint.sh mysqld --port=3307 > logs/db_metadata.log 2>&1 &

echo "Starting db_auth..."
apptainer instance start -B $(pwd)/data/run_postgresql_auth:/var/run/postgresql -B $(pwd)/data/db_auth:/var/lib/postgresql/data -B $(pwd)/auth/schema-sql/auth.sql:/docker-entrypoint-initdb.d/auth.sql -B $(pwd)/auth/configure:/configure sif_images/dynostore_databaseauth_v1.sif db_auth
apptainer exec $KAGIO_ENV --env LANG=C --env LC_ALL=C --env POSTGRES_DB=auth --env POSTGRES_USER=muyalmanager --env POSTGRES_PASSWORD=niCi7unamltrubrlJusp --env ADMIN_USER=dynoadmin --env ADMIN_PASSWORD=XeN5raSsdJkcOMN --env ADMIN_EMAIL=admin@admin instance://db_auth /usr/local/bin/docker-entrypoint.sh postgres -p 5434 > logs/db_auth.log 2>&1 &

echo "Starting db_pub_sub..."
apptainer instance start -B $(pwd)/data/run_postgresql_pubsub:/var/run/postgresql -B $(pwd)/data/db_pub_sub:/var/lib/postgresql/data -B $(pwd)/pub_sub/schema-sql/pub_sub.sql:/docker-entrypoint-initdb.d/pub_sub.sql sif_images/dynostore_dbpubsub_v1.sif db_pub_sub
apptainer exec $KAGIO_ENV --env LANG=C --env LC_ALL=C --env POSTGRES_DB=pub_sub --env POSTGRES_USER=muyalmanager --env POSTGRES_PASSWORD=sicuhowradRaxi5R2ke6 instance://db_pub_sub /usr/local/bin/docker-entrypoint.sh postgres -p 5435 > logs/db_pub_sub.log 2>&1 &

echo "Waiting for databases to initialize..."
sleep 15

# 2. Auth & Pub/Sub
echo "Starting auth..."
apptainer instance start -B $(pwd)/data/run_apache2_auth:/var/run/apache2 -B $(pwd)/data/lock_apache2_auth:/var/lock/apache2 -B $(pwd)/data/log_apache2_auth:/var/log/apache2 -B $(pwd)/apache_configs/auth/ports.conf:/etc/apache2/ports.conf -B $(pwd)/apache_configs/auth/000-default.conf:/etc/apache2/sites-enabled/000-default.conf -B $(pwd)/auth/auth/:/var/www/html/ sif_images/dynostore_auth_v1.sif auth
apptainer exec $KAGIO_ENV --env AUTH_PORT=8090 --env FRONTEND_PORT=8091 --env DB_USER=muyalmanager --env DB_PASSWORD=niCi7unamltrubrlJusp --env DB_NAME=auth --env DB_HOST=localhost --env DB_PORT=5434 instance://auth apache2-foreground > logs/auth.log 2>&1 &

echo "Starting pub_sub..."
apptainer instance start -B $(pwd)/data/run_apache2_pubsub:/var/run/apache2 -B $(pwd)/data/lock_apache2_pubsub:/var/lock/apache2 -B $(pwd)/data/log_apache2_pubsub:/var/log/apache2 -B $(pwd)/apache_configs/pub_sub/ports.conf:/etc/apache2/ports.conf -B $(pwd)/apache_configs/pub_sub/000-default.conf:/etc/apache2/sites-enabled/000-default.conf -B $(pwd)/pub_sub/pub_sub/:/var/www/html/ sif_images/dynostore_pubsub_v1.sif pub_sub
apptainer exec $KAGIO_ENV --env AUTH_HOST=http://localhost:8090 --env METADATA_HOST=http://localhost:8095 --env DB_USER=muyalmanager --env DB_PASSWORD=sicuhowradRaxi5R2ke6 --env DB_NAME=pub_sub --env DB_HOST=localhost --env DB_PORT=5435 --env APIGATEWAY_HOST=localhost:8070 instance://pub_sub apache2-foreground > logs/pub_sub.log 2>&1 &

# 3. Metadata & APIGateway
echo "Starting metadata_server..."
apptainer instance start -B $(pwd)/metadata/app:/var/www sif_images/dynostore_metadata_v3_1.sif metadata_server
apptainer exec --pwd /var/www $KAGIO_ENV --env DB_HOST=localhost --env DB_PORT=3307 --env DB_USERNAME=metadata --env DB_PASSWORD=metadata2023 --env DB_DATABASE=metadata-api --env APIGATEWAY_HOST=localhost:8070 --env AUTH_HOST=localhost:8090 instance://metadata_server sh -c "uvicorn main:app --reload --host 0.0.0.0 --port 8095" > logs/metadata.log 2>&1 &

echo "Starting apigateway..."
apptainer instance start -B $(pwd)/APIGateway/data:/data -B $(pwd)/APIGateway/app:/app sif_images/dynostore_apigateway_v1_1.sif apigateway
apptainer exec instance://apigateway pip install git+https://github.com/dynostore/log_watcher
apptainer exec --pwd /app $KAGIO_ENV --env SQLALCHEMY_DATABASE_URI=sqlite:////data/app.db --env AUTH_HOST=localhost:8090 --env PUB_SUB_HOST=localhost:8093 --env METADATA_HOST=localhost:8095 --env PUBLIC_IP=localhost:8070 --env LOG_WATCHER_LOG_FILE=/app/logs/kagio.log --env LOG_FILES='["/app/logs/dynostore.log"]' instance://apigateway sh -c "logwatcher & hypercorn main:app --bind 0.0.0.0:8070" > logs/apigateway.log 2>&1 &

# 4. Frontend
echo "Starting frontend..."
apptainer instance start -B $(pwd)/data/run_apache2_frontend:/var/run/apache2 -B $(pwd)/data/lock_apache2_frontend:/var/lock/apache2 -B $(pwd)/data/log_apache2_frontend:/var/log/apache2 -B $(pwd)/apache_configs/frontend/ports.conf:/etc/apache2/ports.conf -B $(pwd)/apache_configs/frontend/000-default.conf:/etc/apache2/sites-enabled/000-default.conf -B $(pwd)/frontend/frontend/:/var/www/html/ sif_images/dynostore_frontend_v1.sif frontend
apptainer exec $KAGIO_ENV --env METADATA_HOST=localhost:8095 --env AUTH_HOST=localhost:8090 --env FRONTEND_PORT=8091 --env PUB_SUB_HOST=localhost:8093 --env APIGATEWAY_HOST=localhost:8070 instance://frontend apache2-foreground > logs/frontend.log 2>&1 &

# 5. Data Containers
echo "Starting data containers..."
for i in {1..10}; do
  PORT=$((20000 + i))
  echo "Starting datacontainer$i on port $PORT..."
  apptainer instance start -B $(pwd)/datacontainer/code/:/app -B $(pwd)/datacontainer/objects$i/:/data/objects:rw sif_images/dynostore_datacontainer_v1.sif datacontainer$i
  apptainer exec --pwd /app $KAGIO_ENV --env AUTH_HOST=localhost:8090 --env APIGATEWAY_HOST=localhost:8070 --env DATA_CONTAINER_ID=$i --env LOG_WATCHER_LOG_FILE=/app/logs/kagio$i.log --env LOG_FILES="[\"/app/logs/datacontainer-$i.log\"]" instance://datacontainer$i sh -c "logwatcher & gunicorn --reload --bind 0.0.0.0:$PORT app:app --workers 1 --threads 2 --access-logfile '-' --error-logfile '-' --log-level debug" > logs/datacontainer$i.log 2>&1 &
done

echo "Deployment complete! Use 'apptainer instance list' to view running instances."