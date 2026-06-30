import os
import time
import asyncio
import logging
from threading import Thread

from kagio.kagio import KAGIO
from dynostore.controllers.data import DataController, _log

logger = logging.getLogger(__name__)

KAGIO_BASE_URL = os.getenv("API_BASE_URL", "http://10.18.173.209:8080")
KAGIO_FOXX_URL = os.getenv("KAGIO_FOXX_URL", "http://localhost:8529/_db/_system/kagio")
KAGIO_FOXX_DB = os.getenv("KAGIO_FOXX_DB", "_system")
KAGIO_API_KEY = os.getenv("KAGIO_API_KEY", None)

def start_replicator_daemon():
    thread = Thread(target=replicator_loop, daemon=True)
    thread.start()
    return thread

def replicator_loop():
    # Wait a bit before starting
    time.sleep(10)
    logger.info("Replicator daemon started.")
    
    while True:
        asyncio.run(force_replication_cycle())
        # Parameterized for evaluation: every 5 minutes (300 seconds)
        time.sleep(300)

async def force_replication_cycle():
    metadata_service = os.getenv("METADATA_HOST", "metadata_server")
    pubsub_service = os.getenv("PUB_SUB_HOST", "pub_sub")
    
    logger.info(f"Connecting to KAGIO at {KAGIO_BASE_URL} with Foxx at {KAGIO_FOXX_URL} (DB: {KAGIO_FOXX_DB})")
    
    try:
        kagio_client = KAGIO(
            base_url=KAGIO_BASE_URL,
            foxx_url=KAGIO_FOXX_URL,
            foxx_db=KAGIO_FOXX_DB,
            api_key=KAGIO_API_KEY
        )
    except Exception as e:
        logger.error(f"Failed to initialize KAGIO client: {e}")
        return False

    try:
        logger.info("Polling KAGIO for popular objects...")
        try:
            object_reads = kagio_client.centrality.metadata_indegree()
        except Exception as e:
            logger.error(f"Error fetching indegree from KAGIO: {e}")
            object_reads = []

        # Sort by indegree descending and take top 25
        object_reads.sort(key=lambda x: x.get("indegree", 0), reverse=True)
        top_objects = object_reads[:25]

        for obj_degree in top_objects:
            n_reads = obj_degree.get("indegree", 0)
            if n_reads == 0:
                continue

            obj_id_ori = obj_degree.get("metadata_id", "").replace("metadata_", "")
            if not obj_id_ori:
                continue
            
            # Check if it is already a replica
            if "_r" in obj_id_ori:
                continue

            new_obj_id = obj_id_ori + "_r2"
            
            await replicate_object(obj_id_ori, new_obj_id, n_reads, metadata_service, pubsub_service)
        
        return True
    except Exception as e:
        logger.error(f"Replicator cycle error: {e}")
        return False

async def replicate_object(obj_id_ori, new_obj_id, n_reads, metadata_service, pubsub_service):
    import aiohttp
    import httpx
    
    # 1. Get original object metadata to find owner and original nodes
    url_get_meta = f"http://{metadata_service}/storage/internal/{obj_id_ori}"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url_get_meta)
            if resp.status_code != 200:
                logger.error(f"Could not fetch metadata for {obj_id_ori}")
                return
            data = resp.json()
            if not data.get("exists"):
                return
        except Exception as e:
            logger.error(f"Error fetching metadata for {obj_id_ori}: {e}")
            return
            
    meta = data["metadata"]
    owner = meta["owner"]
    original_nodes = [r.get("chunk", {}).get("server_id") if "chunk" in r else None for r in data.get("nodes", [])]
    original_nodes = [n for n in original_nodes if n is not None]

    # Check if replica exists
    url_replica = f"http://{metadata_service}/storage/internal/{new_obj_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url_replica)
        if resp.status_code == 200 and resp.json().get("exists"):
            logger.info(f"Replica {new_obj_id} already exists.")
            return

    # 2. Pull the original data
    logger.info(f"Replicating {obj_id_ori} to {new_obj_id} (owner={owner})")
    try:
        obj_bytes, status, headers = await DataController.pull_data(owner, obj_id_ori, metadata_service, force_refresh=True)
        if status != 200:
            logger.error(f"Failed to pull {obj_id_ori}: {status}")
            return
    except Exception as e:
        logger.error(f"Exception pulling {obj_id_ori}: {e}")
        return

    # 3. Use an internal wrapper to avoid 'request.body'
    # Since DataController.upload_data takes a Quart request, we will duplicate its logic or create a helper.
    # We will simulate the request dictionary to register the metadata directly
    
    request_json = {
        "name": meta["name"] + "_r2",
        "size": meta["size"],
        "hash": meta["hash"],
        "is_encrypted": meta["is_encrypted"],
        "chunks": 5, # or meta["chunks"]
        "required_chunks": 2, # or meta["required_chunks"]
        "excluded_nodes": original_nodes,
        "indegree": n_reads
    }

    metadata_url = f"http://{metadata_service}/storage/{owner}/system_catalog/{new_obj_id}"
    
    t_meta = time.perf_counter_ns()
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.put(metadata_url, json=request_json)
            if resp.status_code != 201:
                logger.error(f"Failed to register replica metadata: {resp.text}")
                return
            new_nodes = resp.json().get('nodes', [])
            if isinstance(new_nodes, dict):
                new_nodes = new_nodes.get('routes', [])
        except Exception as e:
            logger.error(f"Exception registering replica {new_obj_id}: {e}")
            return
            
    meta_ms = (time.perf_counter_ns() - t_meta) / 1e6
    _log("debug", "UPLOAD_METADATA", new_obj_id, "-", "SUCCESS", f"total_time_ms={meta_ms:.3f}")
            
    # Dispatch EC thread directly
    object_path = f".temp/{new_obj_id}"
    os.makedirs(os.path.dirname(object_path), exist_ok=True)
    t_stream = time.perf_counter_ns()
    with open(object_path, "wb") as f:
        f.write(obj_bytes)
    stream_ms = (time.perf_counter_ns() - t_stream) / 1e6
    
    _log("debug", "UPLOAD_DATA", new_obj_id, "END", "STREAM_OK", f"bytes={len(obj_bytes)};time_ms={stream_ms:.3f}")
        
    try:
        from threading import Thread
        thread = Thread(
            target=DataController._background_erasure_coding,
            args=(object_path, new_obj_id, owner, new_nodes),
            daemon=False
        )
        thread.start()
        _log("info", "UPLOAD_DATA", new_obj_id, "END", "SUCCESS", f"time_upload_ms={stream_ms:.3f};total_time_ms=0.000;chunks={request_json['chunks']};required={request_json['required_chunks']}")
        logger.info(f"Successfully started replication for {new_obj_id} excluding nodes {original_nodes}")
    except Exception as e:
        logger.error(f"Failed to start EC thread for replica: {e}")

