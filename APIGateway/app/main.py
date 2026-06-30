import os
import sys
import subprocess

try:
    import kagio
except ImportError:
    print("Installing kagio missing from SIF image...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "git+https://github.com/CoCo-ARCOS/kagio-client.git"])

import time
import logging
import asyncio
import requests
from uuid import uuid4
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone

from quart import Quart, jsonify, request, render_template, redirect, url_for, session
from quart_auth import AuthUser, login_required, login_user, logout_user, current_user
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy as sa


from dynostore.controllers.auth import AuthController
from dynostore.controllers.catalogs import CatalogController
from dynostore.controllers.data import DataController
from dynostore.controllers.datacontainer import DataContainerController
from dynostore.decorators.token import validateToken, validateAdminToken

from dynostore.db import db

class ISO8601UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat(timespec="milliseconds")  # 2025-09-10T14:47:10.114+00:00

app = Quart(__name__)
app.secret_key = 'supersecret'
app.config["DEBUG"] = True
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024

os.makedirs('/data', exist_ok=True)
sql_alchemy_database_uri = os.getenv('SQLALCHEMY_DATABASE_URI', "sqlite:////data/app.db")

db = QuartSQLAlchemy(
    config=SQLAlchemyConfig(
        binds=dict(
            default=dict(
                engine=dict(
                    url=sql_alchemy_database_uri,
                    echo=True,
                    connect_args=dict(check_same_thread=False),
                ),
                session=dict(
                    expire_on_commit=False,
                ),
            )
        )
    ),
    app=app,
)


LOG_DIR   = os.getenv("LOG_DIR", "./logs")
LOG_FILE  = os.path.join(LOG_DIR, os.getenv("LOG_FILE", "dynostore.log"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
level_int = getattr(logging, LOG_LEVEL, logging.DEBUG)

os.makedirs(LOG_DIR, exist_ok=True)

fmt_str = "%(asctime)s,%(levelname)s,%(name)s,%(message)s"

root = logging.getLogger()
root.setLevel(level_int)
root.handlers.clear()  # optional: avoid duplicate handlers on reload

# Console
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(level_int)
ch.setFormatter(ISO8601UTCFormatter(fmt_str))
root.addHandler(ch)

# Rotating file
fh = RotatingFileHandler(LOG_FILE, maxBytes=50*1024*1024, backupCount=10, encoding="utf-8")
fh.setLevel(level_int)
fh.setFormatter(ISO8601UTCFormatter(fmt_str))
root.addHandler(fh)

# Make sure DataController (and friends) actually emit DEBUG
logging.getLogger("dynostore.controllers.data").setLevel(logging.DEBUG)
logging.getLogger("dynostore.client").setLevel(logging.DEBUG)


class DeviceCode(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(unique=True, nullable=False)
    user_code: Mapped[str] = mapped_column(unique=True, nullable=False)
    expires_at: Mapped[int] = mapped_column(nullable=False)
    interval: Mapped[int] = mapped_column(default=5)
    verified: Mapped[bool] = mapped_column(default=False)
    username: Mapped[str] = mapped_column(nullable=True)


class AccessToken(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, nullable=False)
    username: Mapped[str] = mapped_column(nullable=False)
    expires_at: Mapped[int] = mapped_column(nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "username": self.username,
            "expires_at": self.expires_at
        }


class User(db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    access_token: Mapped[str] = mapped_column(nullable=False)
    user_token: Mapped[str] = mapped_column(nullable=False)
    api_key: Mapped[str] = mapped_column(nullable=False)

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True  # Flask-Login needs this

    def to_dict(self):
        return {
            "username": self.username,
            "access_token": self.access_token,
            "user_token": self.user_token,
            "api_key": self.api_key
        }


AUTH_HOST = os.getenv('AUTH_HOST')
PUB_SUB_HOST = os.getenv('PUB_SUB_HOST')
METADATA_HOST = os.getenv('METADATA_HOST')
PUBLIC_IP = os.getenv('PUBLIC_IP', 'localhost')

db.create_all()

import os
if os.getenv("ENABLE_REPLICATOR", "true").lower() == "true":
    from dynostore.daemons.replicator import start_replicator_daemon
    start_replicator_daemon()


# @app.before_serving
# async def startup():
#     with app.app_context():
#         db.create_all()

# === Endpoint: Force Replication ===
@app.route("/replicate", methods=["POST"])
async def force_replication():
    from dynostore.daemons.replicator import force_replication_cycle
    success = await force_replication_cycle()
    if success:
        return jsonify({"status": "success", "message": "Replication cycle completed"}), 200
    else:
        return jsonify({"status": "error", "message": "Replication cycle failed"}), 500

# === Endpoint: CLI gets a device code ===

@app.route("/device/code", methods=["POST"])
def device_code():
    device_code = str(uuid4())
    user_code = str(uuid4())[:8].upper()
    expires_at = int(time.time()) + 600

    with db.bind.Session() as s:
        with s.begin():
            dc = DeviceCode(
                device_code=device_code,
                user_code=user_code,
                expires_at=expires_at
            )
            s.add(dc)
            s.flush()
            s.refresh(dc)

    return jsonify({
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": f"http://{PUBLIC_IP}/device",
        "expires_in": 600,
        "interval": 5
    })


@app.route("/device", methods=["GET", "POST"])
async def device_entry():
    if request.method == "GET":
        return await render_template("device_verification.html")

    form = await request.form
    user_code = form.get("user_code")

    with db.bind.Session() as s:
        device = s.scalars(sa.select(DeviceCode).filter_by(
            user_code=user_code)).first()
    if not device:
        return "Invalid code", 400

    session["device_code"] = device.device_code
    return await render_template("login.html", device_code=device.device_code)


@app.route("/token/validate", methods=["POST"])
async def verify_token():
    data = await request.get_json() or await request.form
    token = data.get("token")

    if not token:
        return jsonify({"error": "missing_token"}), 400

    with db.bind.Session() as s:
        token_entry = s.scalars(sa.select(AccessToken).filter_by(
            token=token)).first()
        now = int(time.time())
        if token_entry and token_entry.expires_at > now:
            print(token_entry.username, flush=True)
            result = s.scalars(sa.select(User))
            devices = result.all()
            for device in devices:
                print(device)
            user = s.scalars(sa.select(User).filter_by(
                username=token_entry.username)).first()
            print(user, flush=True)
            if not user:
                return jsonify({"error": "user_not_found"}), 404
            return jsonify(user.to_dict()), 200

    return jsonify({"error": "invalid_or_expired_token"}), 401


@app.route("/me")
async def profile():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "missing_token"}), 401

    token = auth.split()[1]
    with app.app_context():
        token_entry = AccessToken.query.filter_by(token=token).first()
        now = int(time.time())
        if not token_entry or token_entry.expires_at <= now:
            return jsonify({"error": "invalid_or_expired_token"}), 401

    return jsonify({"username": token_entry.username, "token": token})


@app.route('/auth/organization/<name>/<acronym>', methods=["PUT"])
async def createOrganization(name, acronym):
    data = await request.get_json()
    url_service = f'http://{AUTH_HOST}/auth/v1/hierarchy'
    payload = {"option": "NEW", "fullname": name,
               "acronym": acronym, "fathers_token": data['fathers_token']}
    results = requests.post(url_service, json=payload)
    return jsonify(results.json()), results.status_code


@app.route('/auth/organization/<name>/<acronym>', methods=["GET"])
async def getOrganization(name, acronym):
    url_service = f'http://{AUTH_HOST}/auth/v1/hierarchy'
    data = {"option": "CHECK", "fullname": name, "acronym": acronym}
    results = requests.post(url_service, json=data)
    return jsonify(results.json()), results.status_code


@app.route('/auth/organization', methods=["GET"])
async def getOrganizations():
    url_service = f'http://{AUTH_HOST}/auth/v1/hierarchy/all/'
    results = requests.get(url_service)
    return jsonify(results.json()), results.status_code


@app.route('/auth/user', methods=["POST"])
async def createUser():
    data = await request.get_json()
    url_service = f'http://{AUTH_HOST}/auth/v1/users/create'
    payload = {
        "option": "NEW",
        "email": data['email'],
        "password": data['password'],
        "username": data['username'],
        "tokenorg": data['tokenorg']
    }
    results = requests.post(url_service, json=payload)
    return jsonify(results.json()), results.status_code


@app.route('/auth/user/<tokenuser>', methods=["GET"])
async def validateUsertToken(tokenuser):
    return AuthController.validateUsertToken(tokenuser, AUTH_HOST)


@app.route("/auth/user/login", methods=["GET", "POST"])
async def login():
    if request.method == "GET":
        return await render_template("login.html")

    inputs = await request.get_json() or await request.form

    if "username" not in inputs or "password" not in inputs:
        return "Missing username or password", 400

    payload = {"user": inputs["username"], "password": inputs["password"]}
    resp = requests.post(
        f"http://{AUTH_HOST}/auth/v1/users/login/", json=payload)

    if resp.status_code == 200:
        user_data = resp.json()["data"]

        if request.args.get("type") == "device":
            form = await request.form
            device_code = form.get("device_code")

            with db.bind.Session() as s:
                device = s.scalars(sa.select(DeviceCode).filter_by(
                    device_code=device_code)).first()

            if not device:
                return "Invalid session", 400

            token = str(uuid4())
            expires_at = int(time.time()) + 3600

            device.verified = True
            device.username = inputs["username"]

            with db.bind.Session() as s:
                with s.begin():
                    dc = AccessToken(
                        token=token,
                        username=inputs["username"],
                        expires_at=expires_at
                    )
                    s.add(dc)

                    s.flush()
                    s.refresh(dc)

                    user = s.scalars(sa.select(User).filter_by(
                        username=user_data["username"])).first()
                    
                    print("User found:", user, flush=True)
                    print(user_data, flush=True)  

                    if not user:
                        user = User(username=user_data["username"], access_token=user_data["access_token"],
                                    user_token=user_data["tokenuser"], api_key=user_data["apikey"])
                        s.add(user)
                    elif user.user_token != user_data["tokenuser"]:
                        user.access_token = user_data["access_token"]
                        user.user_token = user_data["tokenuser"]
                        user.api_key = user_data["apikey"]

                

            return await render_template("auth_success.html", token=token)

        return resp.json(), 200

    return "Invalid credentials", 401


@app.route("/logout")
async def logout():
    logout_user()
    return redirect("/")


@app.route('/pubsub/<tokenuser>/catalog/<catalogname>', methods=["PUT"])
@validateToken(auth_host=AUTH_HOST)
async def createCatalog(tokenuser, catalogname):
    data = await request.get_json()
    return CatalogController.createOrGetCatalog(
        request, PUB_SUB_HOST, catalogname, tokenuser,
        data.get('dispersemode', "SINGLE"),
        data.get('encryption', 0),
        data.get('fathers_token', "/"),
        data.get('processed', 0)
    )


@app.route('/pubsub/<tokenuser>/catalog/<catalog>', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def getCatalog(tokenuser, catalog):
    return CatalogController.getCatalog(PUB_SUB_HOST, catalog, tokenuser)


@app.route('/pubsub/<tokenuser>/catalog/<catalog>', methods=["DELETE"])
@validateToken(auth_host=AUTH_HOST)
async def deleteCatalog(tokenuser, catalog):
    url_service = f'http://{PUB_SUB_HOST}/catalog/{catalog}/?tokenuser={tokenuser}'
    results = requests.delete(url_service)
    return jsonify(results.json()), results.status_code


@app.route('/pubsub/<tokenuser>/catalog/<catalog>/list', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def listCatalogFiles(tokenuser, catalog):
    return CatalogController.listFilesInCatalog(PUB_SUB_HOST, catalog, tokenuser)

@app.route('/pubsub/<tokenuser>/catalogs/subscribed', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def getSubscribedCatalogsRoute(tokenuser):
    return CatalogController.getSubscribedCatalogs(PUB_SUB_HOST, tokenuser)

@app.route('/pubsub/<tokenuser>/catalog/<father>/results', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def getSubCatalogsRoute(tokenuser, father):
    return CatalogController.getSubCatalogs(PUB_SUB_HOST, father)


@app.route('/storage/<tokenuser>/<keyobject>', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def downloadObject(tokenuser, keyobject):
    return await DataController.pull_data(tokenuser, keyobject, METADATA_HOST, PUB_SUB_HOST)


@app.route('/storage/<tokenuser>/<catalog>/<keyobject>', methods=["PUT"])
@validateToken(auth_host=AUTH_HOST)
async def uploadObjectDREX(tokenuser, catalog, keyobject):
    return await DataController.push_data(request, METADATA_HOST, PUB_SUB_HOST, catalog, tokenuser, keyobject)

@app.route('/timeline/<tokenuser>/<keyobject>', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def get_timeline(tokenuser, keyobject):
    return await DataController.get_timeline(tokenuser, keyobject)

@app.route('/metadata/<tokenuser>/<keyobject>', methods=["POST"])
@validateToken(auth_host=AUTH_HOST)
async def upload_metadata(tokenuser, keyobject):
    return await DataController.upload_metadata(request, tokenuser, keyobject)


@app.route('/upload/<tokenuser>/<catalog>/<keyobject>', methods=["PUT"])
@validateToken(auth_host=AUTH_HOST)
async def upload_data(tokenuser, catalog, keyobject):
    return await DataController.upload_data(request, METADATA_HOST, PUB_SUB_HOST, catalog, tokenuser, keyobject)


@app.route('/storage/<tokenuser>/<keyobject>/exists', methods=["GET"])
@validateToken(auth_host=AUTH_HOST)
async def existsObject(tokenuser, keyobject):
    return await DataController.exists_object(tokenuser, keyobject, METADATA_HOST)


@app.route('/storage/<tokenuser>/<keyobject>', methods=["DELETE"])
@validateToken(auth_host=AUTH_HOST)
async def deleteObject(tokenuser, keyobject):
    return DataController.delete_object(request, tokenuser, keyobject, METADATA_HOST)


@app.route('/datacontainer/<admintoken>', methods=["POST"])
@validateAdminToken(auth_host=AUTH_HOST)
async def registDataContainer(admintoken):
    return await DataContainerController.regist(request, admintoken, METADATA_HOST)


@app.route('/datacontainer/<admintoken>/all', methods=["DELETE"])
@validateAdminToken(auth_host=AUTH_HOST)
async def deleteAllDCs(admintoken):
    return await DataContainerController.delete_all(request, admintoken, METADATA_HOST)


@app.route("/statistic/<admintoken>", methods=["GET"])
@validateAdminToken(auth_host=AUTH_HOST)
async def statistics(admintoken):
    url_service = f"http://{METADATA_HOST}/servers/{admintoken}"
    results = requests.get(url_service)
    return jsonify(results.json()), results.status_code


@app.route("/clean/<admintoken>", methods=["GET"])
@validateAdminToken(auth_host=AUTH_HOST)
async def clean(admintoken):
    url_service = f'http://{METADATA_HOST}/servers/clean/all'
    results = requests.get(url_service)
    return jsonify(results.json()), results.status_code

@app.route("/health", methods=["GET"])
async def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    import hypercorn.asyncio
    config = Config()
    config.bind = ["0.0.0.0:80"]
    config.loglevel = "debug"  # ensures Hypercorn’s own logs are verbose
    asyncio.run(hypercorn.asyncio.serve(app, config))
