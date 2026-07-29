import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from core.auth import verify_token
import schemas
from models import File, Server, Abekey
from services.server import allocate, locate, emplazador
from services.server import NODES_REQUIRED_PUSH

router = APIRouter(
    prefix="/storage",
    tags=["storage"]
)

@router.get("/{tokenuser}/{keyfile}/exists", dependencies=[Depends(verify_token)])
async def file_exists(tokenuser: str, keyfile: str, db: Session = Depends(get_db)):
    file_model = db.query(File).filter(
        File.keyfile == keyfile,
        File.removed == False,
        File.owner == tokenuser
    ).first()

    if file_model:
        return {
            "message": "File exists",
            "exists": True,
            "metadata": {
                "name": file_model.name,
                "keyfile": file_model.keyfile,
                "size": file_model.size,
                "hash": file_model.hash,
                "is_encrypted": file_model.is_encrypted,
                "chunks": file_model.chunks,
                "required_chunks": file_model.required_chunks,
                "disperse": file_model.disperse
            }
        }
        return {
            "message": "File not found",
            "exists": False
        }

@router.get("/internal/{keyfile}", dependencies=[])
async def internal_file_info(keyfile: str, db: Session = Depends(get_db)):
    file_model = db.query(File).filter(
        File.keyfile == keyfile,
        File.removed == False
    ).first()

    if file_model:
        try:
            data = await locate(db, file_model.owner, file_model, all_chunks=True)
        except ValueError:
            data = {"routes": []}
        return {
            "message": "File exists",
            "exists": True,
            "metadata": {
                "name": file_model.name,
                "keyfile": file_model.keyfile,
                "size": file_model.size,
                "hash": file_model.hash,
                "is_encrypted": file_model.is_encrypted,
                "chunks": file_model.chunks,
                "required_chunks": file_model.required_chunks,
                "owner": file_model.owner,
                "disperse": file_model.disperse
            },
            "nodes": data.get("routes", [])
        }
    else:
        return {"message": "File not found", "exists": False}

@router.delete("/{tokenuser}/{keyfile}", dependencies=[Depends(verify_token)])
async def delete_file(tokenuser: str, keyfile: str, db: Session = Depends(get_db)):
    file_model = db.query(File).filter(
        File.keyfile == keyfile,
        File.removed == False,
        File.owner == tokenuser
    ).first()

    if not file_model:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        data = await locate(db, tokenuser, file_model)
        servers = data.get("routes", [])
    except Exception:
        servers = []

    error = False
    async with httpx.AsyncClient() as client:
        for srv in servers:
            try:
                response = await client.delete(srv["route"], timeout=5.0)
                if response.status_code != 200:
                    error = True
            except httpx.RequestError:
                error = True

    try:
        file_model.removed = True
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail="Error removing metadata of the file.")

    if error:
        return {"message": "Error deleting file on server. Metadata removed correctly."}
    return {"message": "Metadata and file deleted"}

@router.put("/{tokenuser}/{tokencatalog}/{keyfile}", status_code=201, dependencies=[Depends(verify_token)])
async def push_file(
    tokenuser: str, 
    tokencatalog: str, 
    keyfile: str, 
    payload: schemas.FileCreate, 
    db: Session = Depends(get_db)
):
    print(payload, flush=True)
    nodes = db.query(Server).filter(Server.up == True).all()
    nodes_dict = [
        {"id": n.id, "url": n.url, "memory": n.memory, "storage": n.storage, "up": n.up}
        for n in nodes
    ]

    # Calculate used storage for each node
    for i in range(len(nodes_dict)):
        node_id = nodes_dict[i]["id"]
        # Simplified equivalent of Laravel DB sum queries
        from sqlalchemy import func
        from models import FilesInServer, Chunk
        
        used_fis = db.query(func.sum(File.size)).join(
            FilesInServer, FilesInServer.keyfile == File.keyfile
        ).filter(FilesInServer.server_id == node_id).scalar() or 0.0
        
        used_chunks = db.query(func.sum(Chunk.size)).filter(
            Chunk.server_id == node_id
        ).scalar() or 0.0
        
        nodes_dict[i]["used"] = float(used_fis) + float(used_chunks)

    if not nodes_dict:
        raise HTTPException(status_code=409, detail="Not enough servers to store the file")

    disperse = "SINGLE" if payload.chunks == 1 else "IDA"

    # Register object metadata
    try:
        file_model = db.query(File).filter(File.keyfile == keyfile).first()
        if not file_model:
            file_model = File(keyfile=keyfile)
            db.add(file_model)
        
        file_model.name = payload.name
        file_model.size = payload.size
        file_model.hash = payload.hash
        file_model.is_encrypted = payload.is_encrypted
        file_model.chunks = payload.chunks
        file_model.required_chunks = payload.required_chunks
        file_model.owner = tokenuser
        file_model.disperse = disperse
        db.commit()
        db.refresh(file_model)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


    try:
        data_routes = allocate(db, file_model, nodes_dict, tokenuser, excluded_nodes=payload.excluded_nodes, indegree=payload.indegree)
    except ValueError as e:
        print(e, flush=True)
        raise HTTPException(status_code=400, detail=str(e))

    keys = []
    if file_model.is_encrypted:
        servers_abekeys = emplazador(1, nodes_dict, NODES_REQUIRED_PUSH)
        if servers_abekeys:
            down_link = f"{servers_abekeys[0]['url']}/abekeys/{file_model.keyfile}/{tokenuser}"
            abekey = Abekey(keyfile=file_model.keyfile, url=down_link)
            db.add(abekey)
            db.commit()
            keys.append({"route": down_link})

    return {
        "message": "Object record created or updated",
        "file": {
            "name": file_model.name,
            "keyfile": file_model.keyfile,
            "size": file_model.size,
            "hash": file_model.hash,
            "is_encrypted": file_model.is_encrypted,
            "chunks": file_model.chunks,
            "required_chunks": file_model.required_chunks,
            "owner": file_model.owner,
            "disperse": file_model.disperse
        },
        "nodes": {"routes": data_routes} if isinstance(data_routes, list) else data_routes,
        "keys": keys
    }

@router.put("/drex/{tokenuser}/{tokencatalog}/{keyfile}", status_code=201, dependencies=[Depends(verify_token)])
async def push_file_drex(
    tokenuser: str, 
    tokencatalog: str, 
    keyfile: str, 
    payload: schemas.FileDrexCreate, 
    db: Session = Depends(get_db)
):
    nodes = db.query(Server).filter(Server.up == True).all()
    if not nodes:
        raise HTTPException(status_code=409, detail="Not enough servers to store the file")
        
    nodes_dict = {n.id: {"id": n.id, "url": n.url} for n in nodes}

    disperse = "SINGLE" if payload.chunks == 1 else "IDA"

    try:
        file_model = db.query(File).filter(File.keyfile == keyfile).first()
        if not file_model:
            file_model = File(keyfile=keyfile)
            db.add(file_model)
        
        file_model.name = payload.name
        file_model.size = payload.size
        file_model.hash = payload.hash
        file_model.is_encrypted = payload.is_encrypted
        file_model.chunks = payload.chunks
        file_model.required_chunks = payload.required_chunks
        file_model.owner = tokenuser
        file_model.disperse = disperse
        db.commit()
        db.refresh(file_model)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    result = []
    chunk_size = file_model.size / max(1, file_model.chunks)
    desired_nodes = payload.nodes

    # Keep exactly the logic from PHP
    if len(desired_nodes) < file_model.chunks:
        # Pydantic validation handles this normally, but just to be safe
        raise HTTPException(status_code=400, detail="Missing desired nodes count")

    # The payload.nodes in PHP mapped to indices of `nodes_dict` which is an array
    # Because payload.nodes was an array like [0, 1, 3] representing array indices.
    # PHP: $chunk->server_id = $nodes[$desired_nodes[$i - 1]]["id"];
    # Let's mock the same. We assume `desired_nodes` contains indices of the available nodes.
    nodes_list = list(nodes)

    try:
        for i in range(1, file_model.chunks + 1):
            chunk_name = f"c{i}_{file_model.name}"
            keychunk = str(uuid.uuid4())
            
            node_idx = desired_nodes[i - 1]
            target_node = nodes_list[node_idx]
            
            chunk = Chunk(
                name=chunk_name,
                size=chunk_size,
                keyfile=file_model.keyfile,
                keychunk=keychunk,
                server_id=target_node.id
            )
            db.add(chunk)
            
            route = f"{target_node.url}/objects/{file_model.keyfile}{keychunk}/{tokenuser}"
            result.append({"route": route})
            
        db.commit()
    except IndexError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid node index in drex request.")
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    keys = []
    if file_model.is_encrypted:
        nodes_dict_list = [{"id": n.id, "url": n.url} for n in nodes]
        servers_abekeys = emplazador(1, nodes_dict_list, NODES_REQUIRED_PUSH)
        if servers_abekeys:
            down_link = f"{servers_abekeys[0]['url']}/abekeys/{file_model.keyfile}/{tokenuser}"
            abekey = Abekey(keyfile=file_model.keyfile, url=down_link)
            db.add(abekey)
            db.commit()
            keys.append({"route": down_link})

    return {
        "message": "Object record created or updated",
        "nodes": result,
        "keys": keys
    }

@router.get("/{tokenuser}/{keyfile}", dependencies=[Depends(verify_token)])
async def pull_file(tokenuser: str, keyfile: str, db: Session = Depends(get_db)):
    file_model = db.query(File).filter(
        File.keyfile == keyfile,
        File.removed == False,
        File.owner == tokenuser
    ).first()

    if not file_model:
        raise HTTPException(status_code=404, detail=f"Object {keyfile} not found or not authorized for {tokenuser}")

    try:
        data = await locate(db, tokenuser, file_model, all_chunks=True)
        # Mark original routes
        for r in data.get("routes", []):
            r["is_replica"] = False
            
        # Check for replicas (_r2, _r3, ... until the first missing level)
        # and COMBINE routes to load balance between original and replicas.
        for level in range(2, 12):
            replica_key = f"{keyfile}_r{level}"
            replica_model = db.query(File).filter(
                File.keyfile == replica_key,
                File.removed == False,
                File.owner == tokenuser
            ).first()
            if not replica_model:
                break
            replica_data = await locate(db, tokenuser, replica_model, all_chunks=True)
            for r in replica_data.get("routes", []):
                r["is_replica"] = True
                r["replica_key"] = replica_key
            data["routes"].extend(replica_data.get("routes", []))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    data["file"] = {
        "name": file_model.name,
        "keyfile": file_model.keyfile,
        "size": file_model.size,
        "hash": file_model.hash,
        "is_encrypted": file_model.is_encrypted,
        "chunks": file_model.chunks,
        "required_chunks": file_model.required_chunks,
        "disperse": file_model.disperse
    }

    if file_model.is_encrypted:
        abekey = db.query(Abekey).filter(Abekey.keyfile == keyfile).first()
        data["abekey"] = abekey.url if abekey else None

    return {
        "message": "File record found X",
        "data": data
    }
