FROM python:3.11
ADD code /app
WORKDIR /app
RUN pip install -r requirements.txt
RUN pip install git+https://github.com/dynostore/log_watcher --no-cache-dir

# Copy start.sh
COPY start.sh /start.sh

# Let app user execute start.sh
RUN chmod +x /start.sh

# Create directory for logs
#RUN mkdir -p /app/logs/kagio

#run service
#EXPOSE 5000
#CMD ["python", "app.py"]

# Expose the port Gunicorn will run on
EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:app", "--workers", "4", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]
