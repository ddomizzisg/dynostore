import uuid
import random
import httpx
from sqlalchemy.orm import Session
from models import Chunk, FilesInServer, Server
from fastapi import HTTPException

import os
from kagio.kagio import KAGIO
import math
import random

# Constants
NODES_REQUIRED_PUSH = 5
KAGIO_BASE_URL = os.getenv("API_BASE_URL", "http://10.18.173.209:8080")
KAGIO_FOXX_URL = os.getenv("KAGIO_FOXX_URL", "http://localhost:8529/_db/_system/kagio")
KAGIO_FOXX_DB = os.getenv("KAGIO_FOXX_DB", "_system")
KAGIO_API_KEY = os.getenv("KAGIO_API_KEY", None)

def _norm(vals: list[float]) -> list[float]:
    if not vals:
        return []
    vmin, vmax = min(vals), max(vals)
    if math.isclose(vmin, vmax, rel_tol=1e-12, abs_tol=1e-12):
        return [0.0] * len(vals)
    return [(v - vmin) / (vmax - vmin) for v in vals]

def get_kagio_pageranks() -> dict:
    pr_map = {}
    if os.getenv("ENABLE_KAGIO", "true").lower() != "true":
        return pr_map
    
    try:
        kagio_client = KAGIO(base_url=KAGIO_BASE_URL, foxx_url=KAGIO_FOXX_URL, foxx_db=KAGIO_FOXX_DB, api_key=KAGIO_API_KEY)
        ranks = kagio_client.centrality.data_containers_page_rank()
        for entry in ranks:
            try:
                dc_id = int(str(entry["id"]).replace("datacontainer-", "").replace("dc-", ""))
                pr_map[dc_id] = float(entry["pagerank"])
            except Exception:
                continue
    except Exception as e:
        print(f"Error fetching KAGIO pagerank: {e}")
    return pr_map

def sort_nodes_degree_aware(nodes: list[dict], file_size: float, indegree: int = 0):
    for node in nodes:
        used = node.get("used", 0)
        storage = float(node.get("storage", 1.0)) or 1.0
        node["uf"] = 1.0 - float((storage - (used + file_size)) / storage)

    # Simulator weights
    pr_weight = 0.75
    uf_weight = 0.25
    total_w = uf_weight + pr_weight
    w_uf_default = uf_weight / total_w
    w_pr_default = pr_weight / total_w

    if os.getenv("ENABLE_KAGIO", "true").lower() == "true":
        # Fetch PR from KAGIO
        pr_map = get_kagio_pageranks()

        uf_vals = [node["uf"] for node in nodes]
        pr_vals = [pr_map.get(node["id"], 0.0) for node in nodes]
        
        uf_norm = _norm(uf_vals)
        pr_norm = _norm(pr_vals)
        
        rng = random.Random()
        for i, node in enumerate(nodes):
            epsilon = rng.random() * 1e-6
            node["score"] = (w_uf_default * uf_norm[i]) + (w_pr_default * pr_norm[i]) + epsilon
            
        nodes.sort(key=lambda x: x["score"])
    else:
        nodes.sort(key=lambda x: x["uf"])

def allocate_single(db: Session, file_model, nodes: list[dict], token_user: str, userImpactFactor=0.1, excluded_nodes: list[int] = None, indegree: int = 0):
    if excluded_nodes:
        nodes = [n for n in nodes if n["id"] not in excluded_nodes]
        if not nodes:
            raise ValueError("Not enough nodes after excluding original nodes")
    sort_nodes_degree_aware(nodes, file_model.size, indegree)
    node = nodes[0]
    
    url = f'{node["url"]}/objects/{file_model.keyfile}/{token_user}'
    
    file_in_server = FilesInServer(
        server_id=node["id"],
        keyfile=file_model.keyfile
    )
    db.add(file_in_server)
    db.commit()
    
    return url

def allocate_ida(db: Session, file_model, nodes: list[dict], token_user: str, userImpactFactor: float = 0.1, excluded_nodes: list[int] = None, indegree: int = 0):
    if excluded_nodes:
        nodes = [n for n in nodes if n["id"] not in excluded_nodes]
    
    required_nodes = file_model.chunks
    chunk_size = file_model.size / max(1, file_model.chunks)
    total_nodes = len(nodes)

    if required_nodes > total_nodes:
        raise ValueError("Not enough nodes after exclusion")

    sort_nodes_degree_aware(nodes, file_model.size, indegree)

    result = []
    # From 1 to required_nodes
    for i in range(1, required_nodes + 1):
        chunk_name = f"c{i}_{file_model.name}"
        keychunk = str(uuid.uuid4())
        node = nodes[i - 1]
        
        chunk = Chunk(
            name=chunk_name,
            size=chunk_size,
            keyfile=file_model.keyfile,
            keychunk=keychunk,
            server_id=node["id"]
        )
        db.add(chunk)
        
        route = f'{node["url"]}/objects/{file_model.keyfile}{keychunk}/{token_user}'
        result.append({"route": route})
    
    db.commit()
    return result

def allocate(db: Session, file_model, nodes: list[dict], token_user: str, excluded_nodes: list[int] = None, indegree: int = 0):
    if file_model.disperse in ["IDA", "SIDA"]:
        data = allocate_ida(db, file_model, nodes, token_user, excluded_nodes=excluded_nodes, indegree=indegree)
        return data # returns list of routes
    elif file_model.disperse == "SINGLE":
        url = allocate_single(db, file_model, nodes, token_user, excluded_nodes=excluded_nodes, indegree=indegree)
        return [{"route": url}]
    return []

def locate_single(db: Session, token_user: str, file_model):
    nodes = db.query(FilesInServer, Server).join(
        Server, Server.id == FilesInServer.server_id
    ).filter(
        FilesInServer.keyfile == file_model.keyfile
    ).all()
    
    result = []
    if nodes:
        if os.getenv("ENABLE_KAGIO", "true").lower() == "true":
            pr_map = get_kagio_pageranks()
            # If a server has no PR in the map, default to 1.0 (lowest priority)
            nodes.sort(key=lambda x: pr_map.get(x[1].id, 1.0))
        fis, srv = nodes[0]
        result.append({"route": f"{srv.url}/objects/{file_model.keyfile}/{token_user}"})
    return result

async def locate_ida(db: Session, token_user: str, file_model):
    number_chunks = file_model.chunks
    required_chunks = file_model.required_chunks
    
    chunks_query = db.query(Chunk, Server).join(
        Server, Server.id == Chunk.server_id
    ).filter(
        Chunk.keyfile == file_model.keyfile
    ).all()
    
    if os.getenv("ENABLE_KAGIO", "true").lower() == "true":
        pr_map = get_kagio_pageranks()
        # If a server has no PR in the map, default to 1.0 (lowest priority)
        chunks_query.sort(key=lambda x: pr_map.get(x[1].id, 1.0))
        
    result = []
    i: int = 0

    print(chunks_query, flush=True)
    
    async with httpx.AsyncClient() as client:
        # We need to iterate over chunks and find `required_chunks` healthy servers
        for chunk, srv in chunks_query:
            print(chunk, srv, flush=True)
            if i >= required_chunks:
                break
            
            url = srv.url.rstrip('/') if srv.url.startswith('http') else f"http://{srv.url.rstrip('/')}"
            
            try:
                print(f"URL: {url}", flush=True)
                response = await client.get(f"{url}/health", timeout=3.0)
                print(f"Response: {response.status_code}", flush=True)
                if response.status_code == 200:
                    result.append({
                        "chunk": {
                            "id": chunk.id,
                            "keyfile": chunk.keyfile,
                            "keychunk": chunk.keychunk,
                            "name": chunk.name,
                            "size": chunk.size,
                            "server_id": chunk.server_id
                        },
                        "route": f"{url}/objects/{chunk.keyfile}{chunk.keychunk}/{token_user}",
                        "server": url
                    })
                    i += 1
            except httpx.RequestError as e:
                print(str(e), flush=True)
                print("Error", flush=True)
                continue

    return result

async def locate(db: Session, token_user: str, file_model):
    if file_model.disperse in ["IDA", "SIDA"]:
        servers = await locate_ida(db, token_user, file_model)
        return {"routes": servers}
    elif file_model.disperse == "SINGLE":
        servers = locate_single(db, token_user, file_model)
        if not servers:
            raise ValueError("File not found")
        return {"routes": servers}
    return {}

def emplazador(esferas: int, contenedores: list[dict], total_contenedores: int):
    # Random node selection logic as in original PHP
    if not contenedores or total_contenedores <= 0:
        return []

    indice_contenedores = random.randint(0, total_contenedores - 1)
    resultado_contenedores = []
    
    for i in range(esferas):
        resultado_contenedores.append(contenedores[indice_contenedores])
        indice_contenedores += 1
        if indice_contenedores >= total_contenedores:
            indice_contenedores = 0
            
    return resultado_contenedores
