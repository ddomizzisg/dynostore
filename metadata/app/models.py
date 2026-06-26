from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship
from database import Base
import uuid
from datetime import datetime

class File(Base):
    __tablename__ = "files"

    keyfile = Column(String(400), primary_key=True, index=True)
    name = Column(String(1000))
    size = Column(BigInteger)
    chunks = Column(Integer)
    required_chunks = Column(Integer, default=1)
    is_encrypted = Column(Boolean)
    hash = Column(String(400))
    disperse = Column(String(400))
    removed = Column(Boolean, default=False)
    owner = Column(String(400))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chunks_list = relationship("Chunk", back_populates="file_rel")
    abekeys = relationship("Abekey", back_populates="file_rel")
    files_in_servers = relationship("FilesInServer", back_populates="file_rel")

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255))
    memory = Column(String(255))
    storage = Column(String(255))
    up = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = relationship("Chunk", back_populates="server_rel")
    files_in_servers = relationship("FilesInServer", back_populates="server_rel")

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    keyfile = Column(String(400), ForeignKey("files.keyfile", ondelete="CASCADE"), nullable=False, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    keychunk = Column(String(255), nullable=False)
    name = Column(String(255))
    size = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    file_rel = relationship("File", back_populates="chunks_list")
    server_rel = relationship("Server", back_populates="chunks")

class Abekey(Base):
    __tablename__ = "abekeys"

    id = Column(Integer, primary_key=True, index=True)
    keyfile = Column(String(400), ForeignKey("files.keyfile", ondelete="CASCADE"), nullable=False, index=True)
    url = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    file_rel = relationship("File", back_populates="abekeys")

class FilesInServer(Base):
    __tablename__ = "files_in_servers"

    id = Column(Integer, primary_key=True, index=True)
    keyfile = Column(String(400), ForeignKey("files.keyfile", ondelete="CASCADE"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    file_rel = relationship("File", back_populates="files_in_servers")
    server_rel = relationship("Server", back_populates="files_in_servers")
