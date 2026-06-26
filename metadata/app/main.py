import os
import sys
import subprocess

try:
    import kagio
except ImportError:
    print("Installing kagio missing from SIF image...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "git+https://github.com/CoCo-ARCOS/kagio-client.git"])

from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from database import engine, Base

load_dotenv()

from routers import storage, servers

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Depending on how the production db is created, you might not do this here.
    # Currently assuming tables are already created via Laravel migrations.
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title=os.getenv("APP_NAME", "Metadata API"),
    description="Python FastAPI Migration for Metadata Service",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(storage.router)
app.include_router(servers.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
