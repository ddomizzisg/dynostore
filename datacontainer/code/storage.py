import os
import time

from dynostore.utils.csvlog import make_csv_logger
from dynostore.utils.hardware import get_dir_size

DATA_CONTAINEER_ID = os.getenv("DATA_CONTAINER_ID")
DC_NAME = f"datacontainer_{DATA_CONTAINEER_ID}"

# ----- logging (wrap to prefix status with FS_) -----
_base_log = make_csv_logger(DC_NAME, f"dynostore.{__name__}")

def _log(operation: str, key: str, phase: str, status: str, msg: str = ""):
    # SERVICE, OPERATION, OBJECTKEY, START/END, Status, MSG
    _base_log(operation, key, phase, f"FS_{status}", msg)

def _t0() -> int:
    return time.perf_counter_ns()

def _ms_since(t_start_ns: int) -> float:
    return (time.perf_counter_ns() - t_start_ns) / 1e6

# ------------------------------------------------------------------------------

class StorageManager:
    def delete(self, key: str) -> bool:
        pass

    def read(self, key: str) -> bytes:
        pass

    def write(self, key: str, data: bytes) -> bool:
        pass

    def read_stream(self, key: str):
        pass

    def write_stream(self, key: str, stream) -> dict:
        pass

    def exists(self, key: str) -> bool:
        pass

    def close(self):
        pass


class FileSystemStorage(StorageManager):
    def __init__(self, basepath: str, capacity: int = 10 * 1024**3):
        self.basepath = os.path.abspath(basepath)
        self.capacity = capacity  
        os.makedirs(self.basepath, exist_ok=True)
        self.utilization = get_dir_size(self.basepath)
        

    # --- internals ---
    def _full_path(self, key: str) -> str:
        candidate = os.path.abspath(os.path.join(self.basepath, key))
        # prevent traversal
        if not (candidate == self.basepath or candidate.startswith(self.basepath + os.sep)):
            raise ValueError(f"unsafe_key:{key}")
        return candidate

    # --- API ---
    def delete(self, key: str) -> bool:
        t_total = _t0()
        _log("DELETE", key, "START", "RUN", "")
        try:
            filepath = self._full_path(key)
            # get size for logging and control
            t_stat = _t0()
            size = os.path.getsize(filepath)
            stat_ms = _ms_since(t_stat)
            t_rm = _t0()
            os.remove(filepath)
            rm_ms = _ms_since(t_rm)
            self.utilization -= size
            _log("DELETE", key, "END", "SUCCESS",
                 f"path={filepath},bytes={size},utilization={self.utilization};"
                 f"stat_time_ms={stat_ms:.3f};remove_time_ms={rm_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
            return True
        except FileNotFoundError:
            _log("DELETE", key, "END", "NOT_FOUND", f"total_time_ms={_ms_since(t_total):.3f}")
            return False
        except Exception as e:
            _log("DELETE", key, "END", "ERROR", f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return False

    def read(self, key: str) -> bytes:
        t_total = _t0()
        _log("READ", key, "START", "RUN", "")
        filepath = self._full_path(key)
        try:
            t_read = _t0()
            with open(filepath, 'rb') as f:
                data = f.read()
            read_ms = _ms_since(t_read)
            _log("READ", key, "END", "SUCCESS",
                 f"path={filepath};bytes={len(data)};read_time_ms={read_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
            return data
        except Exception as e:
            _log("READ", key, "END", "ERROR", f"path={filepath};msg={e};total_time_ms={_ms_since(t_total):.3f}")
            raise

    def write(self, key: str, data: bytes) -> bool:
        t_total = _t0()
        
        filepath = self._full_path(key)
        try:
            t_mkdir = _t0()
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            mkdir_ms = _ms_since(t_mkdir)
            t_write = _t0()
            with open(filepath, 'wb') as f:
                f.write(data)
            write_ms = _ms_since(t_write)
            self.utilization += len(data)
            _log("WRITE", key, "END", "SUCCESS",
                 f"path={filepath};bytes={len(data)};utilization={self.utilization};"
                 f"mkdir_time_ms={mkdir_ms:.3f};write_time_ms={write_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
            return True
        except Exception as e:
            _log("WRITE", key, "END", "ERROR",
                 f"path={filepath};msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return False

    def read_stream(self, key: str, chunk_size=8192):
        t_total = _t0()
        _log("READ_STREAM", key, "START", "RUN", "")
        filepath = self._full_path(key)
        
        # Check if exists first before returning generator
        if not os.path.exists(filepath):
            _log("READ_STREAM", key, "END", "NOT_FOUND", f"path={filepath}")
            raise FileNotFoundError(f"File not found: {filepath}")
            
        try:
            def generate():
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                _log("READ_STREAM", key, "END", "SUCCESS", f"path={filepath};total_time_ms={_ms_since(t_total):.3f}")
            return generate()
        except Exception as e:
            _log("READ_STREAM", key, "END", "ERROR", f"path={filepath};msg={e};total_time_ms={_ms_since(t_total):.3f}")
            raise

    def write_stream(self, key: str, stream, chunk_size=8192) -> dict:
        t_total = _t0()
        filepath = self._full_path(key)
        try:
            t_mkdir = _t0()
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            mkdir_ms = _ms_since(t_mkdir)
            
            t_write = _t0()
            bytes_written = 0
            with open(filepath, 'wb') as f:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_written += len(chunk)
            write_ms = _ms_since(t_write)
            self.utilization += bytes_written
            _log("WRITE", key, "END", "SUCCESS",
                 f"path={filepath};bytes={bytes_written};utilization={self.utilization};"
                 f"mkdir_time_ms={mkdir_ms:.3f};write_time_ms={write_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
            return {"bytes": bytes_written, "write_time_ms": write_ms, "total_time_ms": _ms_since(t_total)}
        except Exception as e:
            _log("WRITE", key, "END", "ERROR",
                 f"path={filepath};msg={e};total_time_ms={_ms_since(t_total):.3f}")
            raise

    def exists(self, key: str) -> bool:
        t_total = _t0()
        _log("EXISTS", key, "START", "RUN", "")
        try:
            t_ex = _t0()
            filepath = self._full_path(key)
            ok = os.path.exists(filepath)
            ex_ms = _ms_since(t_ex)
            _log("EXISTS", key, "END", "SUCCESS",
                 f"path={filepath};exists={int(ok)};exists_time_ms={ex_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
            return ok
        except Exception as e:
            _log("EXISTS", key, "END", "ERROR", f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return False

    def close(self):
        t_total = _t0()
        _log("CLOSE", "-", "START", "RUN", "")
        _log("CLOSE", "-", "END", "SUCCESS", f"time_ms={_ms_since(t_total):.3f}")
