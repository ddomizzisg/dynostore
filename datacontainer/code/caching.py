from storage import FileSystemStorage
from dynostore.utils.csvlog import make_csv_logger
import logging
import os
import time

DATA_CONTAINEER_ID = os.getenv("DATA_CONTAINER_ID")
DC_NAME = f"datacontainer_{DATA_CONTAINEER_ID}"

# ----- logging: prefix Status with MEM_ for memory-layer logs -----
_base_log = make_csv_logger(DC_NAME, f"dynostore.{__name__}")


def _log(operation: str, key: str, phase: str, status: str, msg: str = ""):
    # SERVICE, OPERATION, OBJECTKEY, START/END, Status, MSG
    _base_log(operation, key, phase, f"MEM_{status}", msg)


def _t0() -> int:
    return time.perf_counter_ns()


def _ms_since(t_start_ns: int) -> float:
    return (time.perf_counter_ns() - t_start_ns) / 1e6

# ------------------------------------------------------------------------------


class Node:
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCacheStorage:
    def __init__(self, capacity_mem, capacity_fs):
        self.capacity = capacity_mem
        self.utilization = 0
        self.cache = {}
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head
        self.filesystem = FileSystemStorage('/data/objects', capacity=capacity_fs)
        _log("STARTUP", "-", "CONFIGURATION", "RUN",
             f"fs_capacity={self.capacity};fs_utilization={self.utilization};fs_basepath={self.filesystem.basepath};fs_capacity={self.filesystem.capacity};fs_utilization={self.filesystem.utilization}"
        )
        # _log("INIT", "-", "END", "SUCCESS", f"utilization={self.utilization};time_ms={_ms_since(t_total):.3f}")

    def exists(self, key):
        t_total = _t0()
        _log("EXISTS", key, "START", "RUN", "")
        in_mem = key in self.cache
        if in_mem:
            _log("EXISTS", key, "END", "SUCCESS",
                 f"source=memory;exists=1;time_ms={_ms_since(t_total):.3f}")
            return True
        try:
            on_disk = self.filesystem.exists(key)
            _log("EXISTS", key, "END", "SUCCESS",
                 f"source=disk;exists={int(on_disk)};total_time_ms={_ms_since(t_total):.3f}")
            return on_disk
        except Exception as e:
            _log("EXISTS", key, "END", "ERROR",
                 f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            return False

    def evict(self, key):
        t_total = _t0()
        _log("EVICT", key, "START", "RUN",
             f"utilization={self.utilization};capacity={self.capacity}")
        if key in self.cache:
            node = self.cache[key]
            t_mem = _t0()
            self._remove_node(node)
            try:
                if node.value is not None:
                    self.utilization -= len(node.value)
            except Exception:
                pass
            del self.cache[key]
            _log("EVICT", key, "MEM", "SUCCESS",
                 f"source=memory;mem_time_ms={_ms_since(t_mem):.3f}")
        try:
            t_disk = _t0()
            self.filesystem.delete(key)
            _log("EVICT", key, "FS", "SUCCESS",
                 f"source=disk;disk_time_ms={_ms_since(t_disk):.3f};total_time_ms={_ms_since(t_total):.3f}")
        except Exception as e:
            _log("EVICT", key, "END", "ERROR",
                 f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            raise Exception("Error deleting from disk. Exception " + str(e))

    def get(self, key):
        t_total = _t0()
        _log("GET", key, "START", "RUN",
             f"utilization={self.utilization};capacity={self.capacity}")
        if key in self.cache:
            node = self.cache[key]
            t_mv = _t0()
            self._move_to_front(node)
            size = len(node.value) if node.value is not None else 0
            _log("GET", key, "END", "SUCCESS",
                 f"source=memory;bytes={size};move_time_ms={_ms_since(t_mv):.3f};total_time_ms={_ms_since(t_total):.3f}")
            return node.value
        else:
            try:
                t_disk = _t0()
                data = self.filesystem.read(key)
                disk_ms = _ms_since(t_disk)
                bytes_len = len(data) if data is not None else 0
                t_put = _t0()
                self.put(key, data)
                put_ms = _ms_since(t_put)
                _log("GET", key, "END", "SUCCESS",
                     f"source=disk;bytes={bytes_len};disk_time_ms={disk_ms:.3f};put_time_ms={put_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")
                return data
            except Exception as e:
                _log("GET", key, "END", "ERROR",
                     f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
                raise Exception(
                    "Error reading from disk.  Exception " + str(e))

    def put(self, key, value):
        t_total = _t0()
        size = len(value) if value is not None else 0
        
        add_time_ms = 0.0
        evict_time_ms = 0.0
        disk_write_time_ms = 0.0

        while self.utilization + size > self.capacity and self.head.next != self.tail:
            t_ev = _t0()
            _log("PUT", key, "START", "EVICT_REQUIRED",
                    f"utilization={self.utilization};capacity={self.capacity}")
            self._evict()
            evict_time_ms += _ms_since(t_ev)

        node = Node(key, value)
        self.cache[key] = node

        t_add = _t0()
        self._add_to_front(node)
        add_time_ms = _ms_since(t_add)

        self.utilization += size

        _log("PUT", key, "END", "SUCCESS",
                f"utilization={self.utilization};add_time_ms={add_time_ms:.3f};"
                f"evict_time_ms={evict_time_ms:.3f};total_time_ms={_ms_since(t_total):.3f}")

        # write to disk (as in your original code)
        try:
            if key is not None:
                t_wr = _t0()
                self.filesystem.write(key, value)
                disk_write_time_ms = _ms_since(t_wr)
        except Exception as e:
            _log("PUT_WRITE", key, "END", "ERROR", f"msg={e}")
            raise Exception("Error writing to disk.  Exception " + str(e))

        # Build uniform result dictionary
        result = {
            "key": key,
            "bytes": size,
            "caching_ms": add_time_ms + evict_time_ms,             # >0 only when insert path
            "disk_write_time_ms": disk_write_time_ms,  # >0 only on insert (per original behavior)
            "total_time_ms": _ms_since(t_total),
            "utilization": self.utilization,
            "capacity": self.capacity,
        }
        return result

    def get_stream(self, key):
        t_total = _t0()
        _log("GET_STREAM", key, "START", "RUN", "")
        # We bypass the memory cache and stream directly from the filesystem
        try:
            generator = self.filesystem.read_stream(key)
            _log("GET_STREAM", key, "END", "SUCCESS", f"source=disk;total_time_ms={_ms_since(t_total):.3f}")
            return generator
        except Exception as e:
            _log("GET_STREAM", key, "END", "ERROR", f"msg={e};total_time_ms={_ms_since(t_total):.3f}")
            raise Exception("Error reading stream from disk. Exception " + str(e))

    def put_stream(self, key, stream):
        t_total = _t0()
        # For streams, we bypass the memory cache to avoid OOM
        try:
            res = self.filesystem.write_stream(key, stream)
            _log("PUT", key, "END", "SUCCESS", 
                 f"utilization={self.utilization};add_time_ms=0.000;"
                 f"evict_time_ms=0.000;total_time_ms={_ms_since(t_total):.3f}")
            return res
        except Exception as e:
            _log("PUT", key, "END", "ERROR", f"msg={e}")
            raise Exception("Error writing stream to disk. Exception " + str(e))



    def _move_to_front(self, node):
        self._remove_node(node)
        self._add_to_front(node)

    def _add_to_front(self, node):
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node):
        if node.prev is not None:
            node.prev.next = node.next
        if node.next is not None:
            node.next.prev = node.prev
        node.prev = None
        node.next = None

    # remove from memory (and ensure persisted) when capacity exceeded
    def _evict(self):
        t_total = _t0()
        _log("REMOVING_FROM_MEMORY", "-", "START", "RUN",
             f"utilization={self.utilization};capacity={self.capacity}")
        node = self.tail.prev
        if node and node.key is not None:
            try:
                t_wr = _t0()
                # idempotent persist
                self.filesystem.write(node.key, node.value)
                _log("REMOVING_FROM_MEMORY", node.key,
                     "FS", "SUCCESS", f"disk_write_time_ms={_ms_since(t_wr):.3f}")
            except Exception as e:
                _log("REMOVING_FROM_MEMORY", node.key,
                     "END", "ERROR", f"msg={e}")
            try:
                size = len(node.value) if node.value is not None else 0
                self.utilization -= size
            except Exception:
                size = 0
            t_rm = _t0()
            self._remove_node(node)
            rm_ms = _ms_since(t_rm)
            del self.cache[node.key]
            _log("REMOVING_FROM_MEMORY", node.key, "END", "SUCCESS",
                 f"freed_bytes={size};remove_time_ms={rm_ms:.3f};utilization={self.utilization};total_time_ms={_ms_since(t_total):.3f}")
        else:
            _log("REMOVING_FROM_MEMORY", "-", "END", "SUCCESS",
                 f"no_candidate;total_time_ms={_ms_since(t_total):.3f}")
