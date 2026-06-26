from pydantic import BaseModel
from typing import Optional, List, Any

# File Schemas
class FileCreate(BaseModel):
    name: str
    size: int
    hash: str
    is_encrypted: bool
    chunks: int
    required_chunks: int = 1
    excluded_nodes: List[int] = []
    indegree: int = 0

    class Config:
        from_attributes = True

class FileResponse(BaseModel):
    message: str
    file: Optional[Any] = None
    nodes: Optional[Any] = None
    keys: Optional[Any] = None

class FileDrexCreate(FileCreate):
    nodes: List[int]

class FileExistsResponse(BaseModel):
    message: str
    exists: bool
    metadata: Optional[Any] = None

class FilePullResponse(BaseModel):
    message: str
    data: Optional[Any] = None

# Server Schemas
class ServerCreate(BaseModel):
    url: str
    memory: str
    storage: str
    up: bool = False

class ServerResponse(BaseModel):
    id: int
    url: str
    memory: str
    storage: str
    up: bool
    utilization: Optional[float] = None
    n_files: Optional[int] = None

    class Config:
        from_attributes = True
