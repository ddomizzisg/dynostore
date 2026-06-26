FROM python:3.11-slim

# Arguments defined in docker-compose.yml
ARG user=appuser
ARG uid=1000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create system user
RUN useradd -G root -u $uid -m -d /home/$user $user

# Copy start.sh
COPY start.sh /start.sh

# Let app user execute start.sh
RUN chown $user:$user /start.sh
RUN chmod +x /start.sh

# Create directory for logs
#RUN mkdir -p kagio/logs
#RUN chown -R $user:$user kagio/logs

# Set working directory
WORKDIR /var/www

# Copy the python application files
COPY app/ /var/www/

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install git+https://github.com/CoCo-ARCOS/kagio-client.git

RUN pip install git+https://github.com/dynostore/log_watcher

# Change permissions to the user
RUN chown -R $user:$user /var/www

USER $user

EXPOSE 80

# Run FastAPI server
CMD ["sh", "-c", "/start.sh"]
