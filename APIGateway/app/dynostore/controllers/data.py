from json import decoder

import requests
import json
import tempfile
import asyncio
import aiohttp
import os
import numpy as np
import sys
import hashlib
import time
import math
import threading
import shutil
from urllib3.util.retry import Retry
import httpx
import aiofiles
import logging
import fcntl

from requests.adapters import HTTPAdapter

from io import BytesIO
from zfec import Encoder, Decoder

from dynostore.controllers.catalogs import CatalogController
from dynostore.datamanagement.reliability import encoder
from drex.utils.load_data import RealRecords
from drex.utils.prediction import Predictor


logger = logging.getLogger(__name__)


def _log(level: str, operation: str, key: str, phase: str, status: str, msg: str = ""):
    """
    Emit a log in the format:
    SERVICE, OPERATION, OBJECTKEY, START/END, Status, MSG
    """
    rec = f"DATACONTROLLER,{operation},{key},{phase},{status},{msg}"
    level = level.lower()
    if level == "debug":
        logger.debug(rec)
    elif level == "info":
        logger.info(rec)
    elif level == "warning":
        logger.warning(rec)
    elif level == "error":
        logger.error(rec)
    else:
        logger.debug(rec)


def _t0() -> int:
    return time.perf_counter_ns()


def _ms_since(t_start_ns: int) -> float:
    return (time.perf_counter_ns() - t_start_ns) / 1e6


def _merge_timeline_atomic(path: str, update_dict: dict):
    """Atomically merge update_dict into JSON file at path with a file lock."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lock_path = path + ".lock"
    with open(lock_path, "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, "r") as fr:
                    existing = json.load(fr)
            except Exception:
                existing = {}
        existing.update(update_dict)
        # atomic write via temp file + rename
        dir_ = os.path.dirname(path) or "."
        fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".tmp-", text=True)
        try:
            with os.fdopen(fd, "w") as fw:
                json.dump(existing, fw, indent=2)
            os.replace(tmp, path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
        fcntl.flock(lk, fcntl.LOCK_UN)

def read_timeline_atomic(path: str) -> dict:
    """Read timeline JSON atomically (with shared lock)."""
    lock_path = path + ".lock"
    if not os.path.exists(path):
        return {}
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)

    with open(lock_path, "w") as lk:
        # shared lock while reading
        fcntl.flock(lk, fcntl.LOCK_SH)
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)

class DataController:
    predictor = Predictor()
    real_records = RealRecords(dir_data="data/")
    catalog_cache = {}
    CHUNK_SIZE = 64 * 1024  # 64KB

    @staticmethod
    def evict_cache(max_files=100):
        _log("debug", "EVICT_CACHE", "-", "START",
             "INIT", f"max_files={max_files}")
        t_total = _t0()
        cache_dir = ".cache"
        entries = []
        for root, _, files in os.walk(cache_dir):
            for name in files:
                path = os.path.join(root, name)
                try:
                    mtime = os.path.getmtime(path)
                    entries.append((mtime, path))
                except FileNotFoundError:
                    continue
        removed = 0
        if len(entries) > max_files:
            entries.sort()
            for _, path in entries[:-max_files]:
                try:
                    t_rm = _t0()
                    os.remove(path)
                    _log("debug", "EVICT_CACHE", "-", "END", "REMOVE_OK",
                         f"path={path};time_ms={_ms_since(t_rm):.3f}")
                    removed += 1
                except Exception as e:
                    _log("warning", "EVICT_CACHE", "-", "END",
                         "REMOVE_ERROR", f"path={path};msg={e}")
        _log("debug", "EVICT_CACHE", "-", "END", "SUCCESS",
             f"kept={len(entries)-removed};removed={removed};total_time_ms={_ms_since(t_total):.3f}")

    @staticmethod
    def _http_url(route):
        return route if route.startswith("http") else f"http://{route}"

    @staticmethod
    def _get_cache_path(token_user, key_object):
        safe_user = hashlib.sha1(token_user.encode()).hexdigest()
        cache_dir = os.path.join(".cache", safe_user)
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, f"{key_object}.bin")

    @staticmethod
    async def delete_object(token_user, key_object, metadata_service):
        url = f"http://{metadata_service}/storage/{token_user}/{key_object}"
        _log("debug", "DELETE", key_object, "START", "INIT", f"url={url}")
        t_http = _t0()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.delete(url) as resp:
                    payload = await resp.json()
                    _log("debug", "DELETE", key_object, "END", "SUCCESS",
                         f"status={resp.status};http_time_ms={_ms_since(t_http):.3f}")
                    return payload, resp.status
            except Exception as e:
                _log("error", "DELETE", key_object, "END", "ERROR",
                     f"url={url};msg={e};http_time_ms={_ms_since(t_http):.3f}")
                return {"error": str(e)}, 500

    @staticmethod
    async def exists_object(token_user, key_object, metadata_service):
        url = f"http://{metadata_service}/storage/{token_user}/{key_object}/exists"
        _log("debug", "EXISTS", key_object, "START", "INIT", f"url={url}")
        t_http = _t0()
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    payload = await resp.json()
                    _log("debug", "EXISTS", key_object, "END", "SUCCESS",
                         f"status={resp.status};exists={payload.get('exists')};http_time_ms={_ms_since(t_http):.3f}")
                    return payload, resp.status
            except Exception as e:
                _log("error", "EXISTS", key_object, "END", "ERROR",
                     f"url={url};msg={e};http_time_ms={_ms_since(t_http):.3f}")
                return {"error": str(e)}, 500

    @staticmethod
    async def download_chunk(session, route, key_object):
        print(f"Downloading chunk from route: {route}", flush=True)
        chunk_id = 0
        if "chunk" in route:
            try:
                chunk_id = int(route["chunk"]["name"].split("_")[
                               0].replace("c", "")) - 1
            except Exception:
                chunk_id = 0
        if "_r" in key_object:
            try:
                rep_num = key_object.split("_r")[1]
            except Exception:
                rep_num = "1"
        else:
            rep_num = "1"
            
        chunk_str = f"{chunk_id}_{rep_num}"

        url = DataController._http_url(route['route'])
        t0 = _t0()
        _log("debug", "DOWNLOAD_CHUNK", key_object, "START",
             "RUN", f"chunk_id={chunk_str};url={url};attempt=1")
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.read()
        dt_ms = _ms_since(t0)
        _log("debug", "DOWNLOAD_CHUNK", key_object, "END", "SUCCESS",
             f"chunk_id={chunk_id};bytes={len(data)};time_ms={dt_ms:.3f};attempt=1")
        return chunk_id, data

    @staticmethod
    async def pull_data(token_user, key_object, metadata_service, force_refresh=False):
        t_total = _t0()
        _log("debug", "PULL", key_object, "START", "INIT",
             f"user={token_user};force_refresh={force_refresh}")
        decode_start = time.perf_counter_ns()
        timeline_path = f".temp/{key_object}.timeline.json"
        timeline = {}
        timeline["pull_start"] = time.time_ns()

        cache_path = DataController._get_cache_path(token_user, key_object)
        if not force_refresh and os.path.exists(cache_path):
            t_read = _t0()
            with open(cache_path, "rb") as f:
                obj = f.read()
            
            try:
                os.utime(cache_path, None)
            except Exception as e:
                _log("warning", "CACHE_UPDATE_MTIME", key_object, "END", "ERROR", f"msg={e}")

            _log("debug", "PULL", key_object, "END", "CACHE_HIT",
                 f"path={cache_path};bytes={len(obj)};read_time_ms={_ms_since(t_read):.3f};total_time_ms={_ms_since(t_total):.3f}")
            timeline["pull_end"] = time.time_ns()
            os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
            with open(timeline_path, "w") as f:
                json.dump(timeline, f, indent=2)
            return obj, 200, {'Content-Type': 'application/octet-stream', "is_encrypted": False, "time_decode": 0}

        object_path = os.path.join(".temp", key_object)
        marker_path = f"{object_path}.pending"
        if os.path.exists(marker_path):
            _log("debug", "PULL", key_object, "START",
                 "PENDING_MARKER", f"marker={marker_path}")
            object_path = marker_path.replace(".pending", "")
            if os.path.exists(object_path):
                t_read = _t0()
                with open(object_path, "rb") as f:
                    obj = f.read()
                _log("debug", "PULL", key_object, "END", "PENDING_SERVED",
                     f"path={object_path};bytes={len(obj)};read_time_ms={_ms_since(t_read):.3f};total_time_ms={_ms_since(t_total):.3f}")
                timeline["pull_end"] = time.time_ns()
                os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
                with open(timeline_path, "w") as f:
                    json.dump(timeline, f, indent=2)
                return obj, 200, {'Content-Type': 'application/octet-stream', "is_encrypted": False, "time_decode": 0}

        # metadata
        metadata_retrieval_start = time.perf_counter_ns()
        url = f"http://{metadata_service}/storage/{token_user}/{key_object}"
        t_http = _t0()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status >= 400:
                        _log("error", "PULL_METADATA", key_object, "END", "ERROR",
                             f"status={resp.status};url={url};http_time_ms={_ms_since(t_http):.3f}")
                        return await resp.json(), resp.status
                    result = await resp.json()
                    
                routes = result['data'].get('routes', [])
                for route in routes:
                    if 'is_replica' not in route:
                        route['is_replica'] = False
        except Exception as e:
            _log("error", "PULL_METADATA", key_object, "END", "EXCEPTION",
                 f"url={url};msg={e};http_time_ms={_ms_since(t_http):.3f}")
            return {"error": str(e)}, 500
        
        metadata_object = result['data']['file']
        metadata_retrieval_end = time.perf_counter_ns()
        _log("debug", "PULL_METADATA", key_object, "END", "SUCCESS",
             f"routes={len(routes)};is_encrypted={metadata_object.get('is_encrypted')};"
             f"required={metadata_object.get('required_chunks')};total={metadata_object.get('chunks')};"
             f"time_ms={(metadata_retrieval_end - metadata_retrieval_start)/1e6:.3f}")

        # chunks
        chunk_retrieval_start = time.perf_counter_ns()
        try:
            k = metadata_object.get('required_chunks', 1)
            pr_scores = {}
            if os.getenv("ENABLE_KAGIO", "true").lower() == "true":
                cache = getattr(DataController, "_kagio_pr_cache", {})
                cache_time = getattr(DataController, "_kagio_pr_cache_time", 0.0)
                if time.time() - cache_time < 5.0:
                    pr_scores = cache
                else:
                    try:
                        from kagio.kagio import KAGIO
                        KAGIO_API_KEY = os.getenv("KAGIO_API_KEY", "my_token")
                        KAGIO_FOXX_URL = os.getenv("KAGIO_FOXX_URL", "http://kagio-foxx:8529/_db/_system/kagio")
                        KAGIO_FOXX_DB = os.getenv("KAGIO_FOXX_DB", "_system")
                        KAGIO_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
                        kagio_client = KAGIO(base_url=KAGIO_BASE_URL, foxx_url=KAGIO_FOXX_URL, foxx_db=KAGIO_FOXX_DB, api_key=KAGIO_API_KEY)
                        pr_list = await asyncio.to_thread(kagio_client.centrality.data_containers_page_rank)
                        if pr_list and getattr(pr_list, 'data', None):
                            for dc in pr_list.data:
                                dc_name = dc.get("vertex", "").replace("metadata_", "")
                                pr_scores[dc_name] = dc.get("pagerank", 999.0)
                        DataController._kagio_pr_cache = pr_scores
                        DataController._kagio_pr_cache_time = time.time()
                    except Exception as e:
                        try:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Failed to fetch PageRank in pull_data: {e}")
                        except Exception:
                            pass
                        pr_scores = cache

            def get_pr(route):
                try:
                    dc_name = route['route'].split("://")[-1].split("/")[0]
                    return pr_scores.get(dc_name, 999.0)
                except Exception:
                    return 999.0

            # Group by chunk id for robust fallbacks
            routes_by_cid = {}
            for route in routes:
                try:
                    cid = int(route["chunk"]["name"].split("_")[0].replace("c", "")) - 1
                except Exception:
                    cid = 0
                if cid not in routes_by_cid:
                    routes_by_cid[cid] = []
                routes_by_cid[cid].append(route)
                
            unique_cids = list(routes_by_cid.keys())
            
            # Weighted random selection based on KAGIO PR to distribute traffic
            import random
            if os.getenv("ENABLE_KAGIO", "true").lower() == "true":
                # We want to select `k` unique CIDs. We'll assign a weight to each CID based on its best route's PR.
                # Assuming higher PR is better for load balancing (as per original metadata server logic)
                cid_weights = []
                for cid in unique_cids:
                    best_pr = max([get_pr(r) for r in routes_by_cid[cid]])
                    # Use Inverse PageRank! High PR = congested. Low PR = under-utilized replica.
                    # By inverting, we route traffic TO the new replicas and away from the core.
                    cid_weights.append(1.0 / (best_pr + 1e-6))
                
                try:
                    # Select k unique CIDs without replacement based on PR weights
                    # random.choices doesn't support without replacement, so we do it manually
                    selected_cids = []
                    available_cids = list(unique_cids)
                    available_weights = list(cid_weights)
                    
                    while len(selected_cids) < k and available_cids:
                        chosen = random.choices(available_cids, weights=available_weights, k=1)[0]
                        selected_cids.append(chosen)
                        idx = available_cids.index(chosen)
                        available_cids.pop(idx)
                        available_weights.pop(idx)
                    unique_cids = selected_cids
                except Exception:
                    # Fallback to simple shuffle if PR weights fail
                    random.shuffle(unique_cids)
            else:
                random.shuffle(unique_cids)
            
            async with aiohttp.ClientSession() as session_reqs:
                async def fetch_with_fallback(cid):
                    for route in routes_by_cid.get(cid, []):
                        target_key = key_object + "_r2" if route.get('is_replica') else key_object
                        try:
                            return await DataController.download_chunk(session_reqs, route, target_key)
                        except Exception:
                            continue
                    raise Exception(f"All container routes for chunk {cid} failed.")
                    
                # Request exactly k unique chunks
                tasks = [fetch_with_fallback(cid) for cid in unique_cids[:k]]
                results = await asyncio.gather(*tasks)
        except Exception as e:
            _log("error", "PULL_CHUNKS", key_object,
                 "END", "ERROR", f"msg={e}")
            return {"error": str(e)}, 500
        chunk_retrieval_end = time.perf_counter_ns()
        _log("debug", "PULL_CHUNKS", key_object, "END", "SUCCESS",
             f"count={len(results)};time_ms={(chunk_retrieval_end - chunk_retrieval_start)/1e6:.3f}")

        # reconstruct
        object_reconstruction_start = time.perf_counter_ns()
        try:
            if metadata_object["required_chunks"] == 1:
                obj = results[0][1]
                _log("debug", "RECONSTRUCT", key_object,
                     "END", "SIMPLE", f"bytes={len(obj)}")
            else:
                sorted_results = sorted(results, key=lambda x: x[0])
                chunk_data = [
                    data for _, data in sorted_results[:metadata_object['required_chunks']]]
                
                chunk_indices = [
                    idx for idx, _ in sorted_results[:metadata_object['required_chunks']]]
                
                k = metadata_object['required_chunks']
                n = metadata_object['chunks']
                
                original_size = metadata_object.get('size')
                t_decode = _t0()
                decoder = Decoder(k, n)

                # Call the decoder
                recovered_blocks = decoder.decode(chunk_data, chunk_indices)

                decode_ms = _ms_since(t_decode)
                obj = b''.join(recovered_blocks)
                if original_size is not None:
                    obj = obj[:int(original_size)]
                _log("debug", "RECONSTRUCT", key_object, "END", "EC",
                     f"k={k};n={n};bytes={len(obj)};orig_size={original_size};decode_time_ms={decode_ms:.3f}")
        except Exception as e:
            print(e, flush=True)
            _log("error", "RECONSTRUCT", key_object,
                 "END", "ERROR", f"msg={e}")
            return {"error": str(e)}, 500
        object_reconstruction_end = time.perf_counter_ns()
        _log("debug", "RECONSTRUCT", key_object, "END", "DONE",
             f"time_ms={(object_reconstruction_end - object_reconstruction_start)/1e6:.3f}")

        # cache write
        object_caching_start = time.perf_counter_ns()
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            t_write = _t0()
            with open(cache_path, "wb") as f:
                f.write(obj)
            os.utime(cache_path, None)
            _log("debug", "CACHE_WRITE", key_object, "END", "SUCCESS",
                 f"path={cache_path};bytes={len(obj)};time_ms={_ms_since(t_write):.3f}")
            
            # Evict cache in the background to enforce a limit on the number of cached objects
            import threading
            max_files = int(os.environ.get("CACHE_MAX_FILES", 100))
            threading.Thread(target=DataController.evict_cache, kwargs={"max_files": max_files}, daemon=True).start()
        except Exception as e:
            _log("warning", "CACHE_WRITE", key_object, "END", "ERROR",
                 f"path={cache_path};msg={e}")

        # timeline
        object_caching_end = time.perf_counter_ns()
        timeline["Object caching"] = {
            "start": object_caching_start, "end": object_caching_end}
        timeline["Chunk retrieval"] = {
            "start": chunk_retrieval_start, "end": chunk_retrieval_end}
        timeline["Object reconstruction"] = {
            "start": object_reconstruction_start, "end": object_reconstruction_end}
        timeline["Metadata retrieval"] = {
            "start": metadata_retrieval_start, "end": metadata_retrieval_end}

        decode_end = time.perf_counter_ns()
        timeline["pull_end"] = time.time_ns()
        try:
            os.makedirs(os.path.dirname(timeline_path), exist_ok=True)
            t_tw = _t0()
            with open(timeline_path, "w") as f:
                json.dump(timeline, f, indent=2)
            _log("debug", "TIMELINE_WRITE", key_object, "END", "SUCCESS",
                 f"path={timeline_path};time_ms={_ms_since(t_tw):.3f}")
        except Exception as e:
            _log("warning", "TIMELINE_WRITE", key_object, "END", "ERROR",
                 f"path={timeline_path};msg={e}")

        _log("debug", "PULL", key_object, "END", "SUCCESS",
             f"total_time_ms={_ms_since(t_total):.3f};total_decode_ns={decode_end - decode_start}")
        
        return obj, 200, {
            'Content-Type': 'application/octet-stream',
            "is_encrypted": metadata_object['is_encrypted'],
            "time_decode": decode_end - decode_start
        }

    @staticmethod
    def _resilient_distribution(object_id, data_bytes, token_user):
        chunk_start = time.perf_counter_ns()
        
        k, n = 2, 5
        encoder_obj = Encoder(k, n)

        if len(data_bytes) == 0:
            _log("error", "EC_SPLIT", "-", "END", "ERROR", "empty_input")
            raise ValueError("Input file is empty")

        block_size = int(math.ceil(len(data_bytes) / float(k)))
        buf = np.frombuffer(data_bytes, dtype=np.uint8)
        pad_len = block_size * k - len(buf)
        buf = np.pad(buf, (0, pad_len), constant_values=0)
        blocks = [buf[i * block_size:(i + 1) * block_size].tobytes()
                  for i in range(k)]

        t_encode = _t0()
        fragments = encoder_obj.encode(blocks)
        enc_ms = _ms_since(t_encode)
        dt_ms = (time.perf_counter_ns() - chunk_start) / 1e6
        _log("debug", "EC_SPLIT", object_id, "END", "SUCCESS",
             f"input_size={len(data_bytes)};k={k};n={n};block_size={block_size};fragments={len(fragments)};encode_time_ms={enc_ms:.3f};total_time_ms={dt_ms:.3f}")

        return fragments, n, k, int(dt_ms * 1e6)

    @staticmethod
    async def _upload_chunk(session, url, data):
        _log("debug", "UPLOAD_CHUNK", "-", "START",
             "RUN", f"url={url};bytes={len(data)}")
        t_http = _t0()
        try:
            async with session.put(url, data=data) as resp:
                if resp.status != 201:
                    _log("error", "UPLOAD_CHUNK", "-", "END", "ERROR",
                         f"url={url};status={resp.status};http_time_ms={_ms_since(t_http):.3f}")
                    raise Exception(f"Upload failed to {url}: {resp.status}")
                _log("debug", "UPLOAD_CHUNK", "-", "END", "SUCCESS",
                     f"url={url};status={resp.status};http_time_ms={_ms_since(t_http):.3f}")
        except Exception as e:
            _log("error", "UPLOAD_CHUNK", "-", "END", "EXCEPTION",
                 f"url={url};msg={e};http_time_ms={_ms_since(t_http):.3f}")
            raise e

    @staticmethod
    def _get_cached_catalog(token_user, catalog):
        return DataController.catalog_cache.get((token_user, catalog))

    @staticmethod
    def _set_cached_catalog(token_user, catalog, catalog_result):
        DataController.catalog_cache[(token_user, catalog)] = catalog_result

    @staticmethod
    def _background_erasure_coding(object_path, key_object, token_user, nodes):
        t_total = _t0()
        _log("debug", "EC", key_object, "START", "INIT",
             f"path={object_path};nodes={len(nodes) if isinstance(nodes, list) else 'N/A'}")

        timeline_path = f".temp/{key_object}.timeline.json"
        marker_path = f"{object_path}.pending"

        # mark EC started
        _merge_timeline_atomic(timeline_path, {
            "coding_status": "in_progress",
            "ec_worker_pid": os.getpid(),
            "ec_worker_tid": threading.get_ident(),
            "ec_dispatch_time_ns": time.time_ns()
        })

        try:
            # read file
            t_read = _t0()
            ec_start = time.time_ns()
            with open(object_path, "rb") as f:
                data_bytes = f.read()
            read_ms = _ms_since(t_read)

            # split into fragments
            fragments, n, k, chunk_time = DataController._resilient_distribution(
                key_object, data_bytes, token_user
            )
            ec_end = time.time_ns()

            # safety: nodes available?
            if not isinstance(nodes, list):
                raise TypeError(
                    f"nodes must be a list of node dicts; got {type(nodes)}")
            if len(fragments) > len(nodes):
                raise ValueError(
                    f"Not enough nodes: fragments={len(fragments)} > nodes={len(nodes)}")

            # prepare HTTP session with retries/timeouts
            retry = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 503, 504),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session = requests.Session()
            session.mount("http://", adapter)
            session.mount("https://", adapter)

            # push fragments
            fragment_push_start = time.time_ns()
            server_info = []
            for i, fragment in enumerate(fragments):
                url = DataController._http_url(nodes[i]['route'])
                try:
                    t_http = _t0()
                    res = session.put(url, data=fragment, timeout=10)
                    http_ms = _ms_since(t_http)
                    if res.status_code != 201:
                        _log("error", "EC_PUSH", key_object, "END", "ERROR",
                             f"frag={i};url={url};status={res.status_code};time_ms={http_ms:.3f};body={res.text[:256]}")
                    else:
                        _log("debug", "EC_PUSH", key_object, "END", "SUCCESS",
                             f"frag={i};url={url};status={res.status_code};bytes={len(fragment)};time_ms={http_ms:.3f}")
                        server_info.append(res.json()["data"])
                except Exception as e:
                    _log("error", "EC_PUSH", key_object, "END", "EXCEPTION",
                         f"frag={i};url={url};msg={e}")
                    raise e
            fragment_push_end = time.time_ns()

            # remove marker only on success
            if os.path.exists(marker_path):
                try:
                    t_rm = _t0()
                    os.remove(marker_path)
                except Exception as e:
                    _log("warning", "PASSIVE_EC_MARKER", key_object, "END", "REMOVE_ERROR",
                         f"marker={marker_path};msg={e}")

            # write timeline (atomic merge)
            _merge_timeline_atomic(timeline_path, {
                "erasure_coding": {"start": ec_start, "end": ec_end, "n": n, "k": k,
                                   "split_ms": chunk_time/1e6 if chunk_time else None,
                                   "read_ms": read_ms},
                "fragment_push": {"start": fragment_push_start, "end": fragment_push_end},
                "servers_info": server_info,
                "coding_status": "completed",
                "ec_total_time_ms": _ms_since(t_total)
            })

            _log("info", "EC", key_object, "END", "DONE",
                 f"read_time_ms={read_ms:.3f};ec_split_ms={chunk_time/1e6:.2f};total_time_ms={_ms_since(t_total):.3f}")

        except Exception as e:
            # mark failed; keep marker (so a re-try daemon can pick it up)
            _merge_timeline_atomic(timeline_path, {
                "coding_status": "failed",
                "ec_error": str(e),
                "ec_total_time_ms": _ms_since(t_total)
            })
            _log("error", "PASSIVE_EC", key_object, "END", "ERROR", f"msg={e}")

    # -------------------------------
    # UPLOAD METADATA (fixed: no double-encoding)
    # -------------------------------
    @staticmethod
    async def upload_metadata(request, token_user, key_object):
        t_total = _t0()
        timeline_path = f".temp/{key_object}.timeline.json"
        upload_meta_start = time.time_ns()
        
        metadata_path = f".temp/{key_object}.json"
        raw = await request.get_data()
        size = len(raw) if raw else 0
        try:
            t_write = _t0()
            parsed = json.loads(raw) if raw else {}
            os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
            with open(metadata_path, "w") as f:
                json.dump(parsed, f)
            _log("debug", "UPLOAD_METADATA", key_object, "-", "SUCCESS",
                 f"total_time_ms={_ms_since(t_write):.3f}")
        except Exception as e:
            _log("error", "UPLOAD_METADATA", key_object, "-", "ERROR",
                 f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return {"error": str(e)}, 500

        upload_meta_end = time.time_ns()
        _merge_timeline_atomic(timeline_path, {
            "upload_metadata": {"start": upload_meta_start, "end": upload_meta_end}
        })

        
        return {"status": "metadata received"}, 200


    @staticmethod
    async def upload_data(request, metadata_service, pubsub_service, catalog, token_user, key_object):
        t_total = _t0()

        timeline_path = f".temp/{key_object}.timeline.json"
        _merge_timeline_atomic(timeline_path, {"upload_start": time.time_ns()})
        perf_start = time.perf_counter_ns()

        # check metadata presence
        metadata_path = f".temp/{key_object}.json"
        if not os.path.exists(metadata_path):
            _log("error", "UPLOAD_DATA", key_object, "END", "MISSING_METADATA",
                 f"path={metadata_path};total_time_ms={_ms_since(t_total):.3f}")
            return {"error": "Missing metadata for object"}, 400

        # load request metadata JSON
        with open(metadata_path) as f:
            request_json = json.load(f)
        if isinstance(request_json, str):
            request_json = json.loads(request_json)

        # stream file to disk
        object_path = f".temp/{key_object}"
        os.makedirs(os.path.dirname(object_path), exist_ok=True)
        stream_start = time.time_ns()
        total_bytes = 0
        try:
            t_stream = _t0()
            async with aiofiles.open(object_path, "wb") as f:
                # Prefer request.body as async iterator if your framework provides it
                # keeping your original pattern:
                async for data in request.body:
                    total_bytes += len(data)
                    await f.write(data)
            stream_ms = _ms_since(t_stream)
        except Exception as e:
            _log("error", "UPLOAD_DATA", key_object, "END", "STREAM_ERROR",
                 f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return {"error": str(e)}, 500
        stream_end = time.time_ns()
        _merge_timeline_atomic(
            timeline_path, {"stream": {"start": stream_start, "end": stream_end}})
        _log("debug", "UPLOAD_DATA", key_object, "END", "STREAM_OK",
             f"bytes={total_bytes};time_ms={stream_ms:.3f}")

        # marker (indicates EC pending)
        marker_path = f"{object_path}.pending"
        try:
            t_mk = _t0()
            with open(marker_path, "w") as marker:
                marker.write("pending")
        except Exception as e:
            _log("warning", "UPLOAD_DATA", key_object, "END", "MARKER_WRITE_ERROR",
                 f"marker={marker_path};msg={e}")

        # catalog: create or get
        catalog_start = time.time_ns()
        perf_catalog_start = time.perf_counter_ns()
        catalog_result, status = CatalogController.createOrGetCatalog(
            request, pubsub_service, catalog, token_user
        )
        perf_catalog_end = time.perf_counter_ns()
        catalog_end = time.time_ns()

        _merge_timeline_atomic(timeline_path, {
            "catalog": {"start": catalog_start, "end": catalog_end},
            "catalog_perf": perf_catalog_end - perf_catalog_start
        })

        if status not in [201, 302]:
            _log("error", "UPLOAD_DATA", key_object, "END", "CATALOG_ERROR",
                 f"status={status};result={catalog_result};total_time_ms={_ms_since(t_total):.3f}")
            return catalog_result, status

        token_catalog = catalog_result['data']['tokencatalog']

        # set status fields; chunks/k can later be aligned with EC results
        request_json['chunks'] = 5
        request_json['required_chunks'] = 2
        request_json['coding_status'] = 'pending'

        # register metadata (async HTTP)
        metadata_url = f"http://{metadata_service}/storage/{token_user}/{token_catalog}/{key_object}"
        metadata_start = time.time_ns()
        try:
            t_http = _t0()
            print("req_json", request_json, flush=True)
            print("metadata_url", metadata_url, flush=True)
            print("payload", json.dumps(request_json), flush=True)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.put(metadata_url, json=request_json)
            http_ms = _ms_since(t_http)
        except Exception as e:
            _log("error", "UPLOAD_DATA", key_object, "END", "METADATA_REGISTER_EXCEPTION",
                 f"url={metadata_url};msg={e}")
            return {"error": str(e)}, 500
        metadata_end = time.time_ns()

        if resp.status_code != 201:
            try:
                body = resp.json()
            except Exception:
                body = {"error": resp.text[:256]}
            _log("error", "UPLOAD_DATA", key_object, "END", "METADATA_REGISTER_ERROR",
                 f"status={resp.status_code};body={body}")
            return body, resp.status_code

        print("Metadata registered successfully", resp.json(), flush=True)
        nodes = resp.json().get('nodes', []).get('routes', [])

        print("NODES for EC:", nodes, flush=True)


        # Dispatch EC thread (non-daemon)
        ec_thread_start = time.time_ns()
        try:
            # thread = threading.Thread(
            #     target=DataController._background_erasure_coding,
            #     args=(object_path, key_object, token_user, nodes),  # <-- fixed
            #     daemon=False
            # )
            # thread.start()
            DataController._background_erasure_coding(object_path, key_object, token_user, nodes)
            _merge_timeline_atomic(timeline_path, {
                "ec_thread_dispatch": {"start": ec_thread_start},
                "coding_status": "in_progress"
            })
            _log("debug", "UPLOAD_DATA", key_object,
                 "END", "EC_THREAD_DISPATCHED", "")
        except Exception as e:
            _log("warning", "UPLOAD_DATA", key_object,
                 "END", "EC_THREAD_ERROR", f"msg={e}")
            _merge_timeline_atomic(timeline_path, {
                "coding_status": "failed",
                "ec_error": f"thread_start: {e}"
            })

        # register into catalog (post-stream)
        t_reg = _t0()
        results, status = CatalogController.registFileInCatalog(
            pubsub_service, catalog_result["data"]["tokencatalog"], token_user, key_object
        )
        reg_ms = _ms_since(t_reg)
        if status != 200:
            _log("warning", "UPLOAD_DATA", key_object, "END", "CATALOG_REGISTER_ERROR",
                 f"status={status};result={results};time_ms={reg_ms:.3f}")
        
        # finalize upload timing
        total_perf = time.perf_counter_ns() - perf_start
        _merge_timeline_atomic(timeline_path, {
            "upload_end": time.time_ns(),
            "upload_total_perf_ns": total_perf
        })

        _log("info", "UPLOAD_DATA", key_object, "END", "SUCCESS",
             f"time_upload_ms={total_perf/1e6:.3f};total_time_ms={_ms_since(t_total):.3f};chunks={request_json['chunks']};required_chunks={request_json['required_chunks']}")

        return {
            "key_object": key_object,
            "passive_ec": True,
            "time_upload": round(total_perf / 1e6, 3)
        }, 201

    @staticmethod
    async def get_timeline(token_user, key_object):
        """Return the timeline content for a given object via HTTP."""
        t_total = _t0()
        timeline_path = f".temp/{key_object}.timeline.json"
        _log("debug", "GET_TIMELINE", key_object, "START", "INIT", f"user={token_user}")

        try:
            data = read_timeline_atomic(timeline_path)
            if not data:
                _log("warning", "GET_TIMELINE", key_object, "END", "EMPTY_OR_MISSING",
                     f"path={timeline_path};total_time_ms={_ms_since(t_total):.3f}")
                return {"error": "Timeline not found or empty"}, 404

            _log("debug", "GET_TIMELINE", key_object, "END", "SUCCESS",
                 f"path={timeline_path};keys={list(data.keys())};time_ms={_ms_since(t_total):.3f}")
            return data, 200
        except Exception as e:
            _log("error", "GET_TIMELINE", key_object, "END", "ERROR",
                 f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return {"error": str(e)}, 500