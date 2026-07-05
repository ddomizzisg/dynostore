# Data container API

import os
import sys
import logging
from flask import Flask, jsonify, request, Response, stream_with_context
import requests
from werkzeug.utils import secure_filename
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

from dynostore.decorators.token import validateToken
from caching import LRUCacheStorage
from dynostore.utils.csvlog import make_csv_logger

class ISO8601UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat(timespec="milliseconds")  # 2025-09-10T14:47:10.114+00:00

DATA_CONTAINEER_ID = os.getenv("DATA_CONTAINER_ID")
DC_NAME = f"datacontainer_{DATA_CONTAINEER_ID}"

# ----- logging (safe default; won't double-configure if app sets handlers) -----
LOG_DIR = os.getenv("LOG_DIR", "./logs")
LOG_FILE = os.path.join(LOG_DIR, os.getenv("LOG_FILE", f"datacontainer-{DATA_CONTAINEER_ID}.log"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
level_int = getattr(logging, LOG_LEVEL, logging.DEBUG)

os.makedirs(LOG_DIR, exist_ok=True)

fmt_str = "%(asctime)s,%(levelname)s,%(name)s,%(message)s"

root = logging.getLogger()
root.setLevel(level_int)
root.handlers.clear()

# Console
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(level_int)
ch.setFormatter(ISO8601UTCFormatter(fmt_str))
root.addHandler(ch)

# Rotating file
fh = RotatingFileHandler(LOG_FILE, maxBytes=50 * 1024 * 1024, backupCount=10, encoding="utf-8")
fh.setLevel(level_int)
fh.setFormatter(ISO8601UTCFormatter(fmt_str))  # <-- was ch.setFormatter(...)
root.addHandler(fh)

# If make_csv_logger creates its own logger, ensure it propagates or give it no handlers:
csv_log = logging.getLogger(f"dynostore.{__name__}")
csv_log.propagate = True  # so it uses root's handlers/formatters

_log = make_csv_logger(DC_NAME, f"dynostore.{__name__}") 

# ------------------------------------------------------------------------------

app = Flask(__name__)
app.config["DEBUG"] = True

AUTH_HOST = os.getenv('AUTH_HOST')
URL_AUTH = "http://" + AUTH_HOST + '/auth/v1/user?tokenuser=' if AUTH_HOST else None

# initialize storage with 2GB of memory and 20GB of filesystem
storage = LRUCacheStorage(2 * 1024**3, 20 * 1024**3)

# check if node is alive
@app.route('/health', methods=["GET"])
def health():
    _log("HEALTH", "-", "START", "RUN", "")
    resp = jsonify({"message": "Data container is alive"}), 200
    _log("HEALTH", "-", "END", "SUCCESS", "status=200", level="info")
    return resp

@app.route('/objects/<objectkey>/<tokenuser>', methods=["PUT"])
@validateToken(auth_host=AUTH_HOST)
def upload_object(objectkey, tokenuser):
    if request.method == 'PUT':
        try:
            res = storage.put_stream(objectkey, request.stream)
            _log("UPLOAD", objectkey, "END", "SUCCESS", f"bytes={res.get('bytes', 0)};", level="info")
            return jsonify({"message": "Data successfully uploaded", "data": res}), 201
        except Exception as e:
            _log("UPLOAD", objectkey, "END", "ERROR", f"msg={e};status=500", level="error")
            return jsonify({"error": f"Error uploading data. Exception {e}"}), 500
    else:
        _log("UPLOAD", objectkey, "END", "ERROR", "invalid_method;status=405", level="warning")
        return jsonify({"error": "Invalid request method"}), 405

@app.route('/objects/<objectkey>/<tokenuser>', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
def download_object(objectkey, tokenuser):
    _log("DOWNLOAD", objectkey, "START", "RUN", f"user={tokenuser}")
    if request.method == 'GET':
        try:
            generator = storage.get_stream(objectkey)
            _log("DOWNLOAD", objectkey, "END", "SUCCESS", f"status=200", level="info")
            return Response(stream_with_context(generator)), 200
        except Exception as e:
            _log("DOWNLOAD", objectkey, "END", "ERROR", f"msg={e};status=500", level="error")
            return jsonify({"error": f"Error downloading data. Exception {e}"}), 500
    else:
        _log("DOWNLOAD", objectkey, "END", "ERROR", "invalid_method;status=405", level="warning")
        return jsonify({"error": "Invalid request method"}), 405

@app.route('/objects/<objectkey>/<tokenuser>', methods=["DELETE"])
@validateToken(auth_host=AUTH_HOST)
def delete_object(objectkey, tokenuser):
    _log("DELETE", objectkey, "START", "RUN", f"user={tokenuser}")
    if request.method == 'DELETE':
        try:
            storage.evict(objectkey)
            _log("DELETE", objectkey, "END", "SUCCESS", "status=200", level="info")
            return jsonify({"message": "Data successfully deleted"}), 200
        except Exception as e:
            _log("DELETE", objectkey, "END", "ERROR", f"msg={e};status=500", level="error")
            return jsonify({"error": f"Error deleting data. Exception {e}"}), 500
    else:
        _log("DELETE", objectkey, "END", "ERROR", "invalid_method;status=405", level="warning")
        return jsonify({"error": "Invalid request method"}), 405

@app.route('/objects/<objectkey>/<tokenuser>', methods=["HEAD"])
@validateToken(auth_host=AUTH_HOST)
def head_object(objectkey, tokenuser):
    _log("HEAD", objectkey, "START", "RUN", f"user={tokenuser}")
    if request.method == 'HEAD':
        exists = storage.exists(objectkey)
        if exists:
            _log("HEAD", objectkey, "END", "SUCCESS", "exists=1;status=200", level="info")
            return jsonify({"message": "Data exists"}), 200
        else:
            _log("HEAD", objectkey, "END", "SUCCESS", "exists=0;status=404", level="info")
            return jsonify({"error": "Data does not exist."}), 404
    else:
        _log("HEAD", objectkey, "END", "ERROR", "invalid_method;status=405", level="warning")
        return jsonify({"error": "Invalid request method"}), 405

if __name__ == '__main__':
    _log("STARTUP", "-", "START", "INIT", f"debug={app.config.get('DEBUG')}", level="info")
    app.run(debug=True, host='0.0.0.0')
