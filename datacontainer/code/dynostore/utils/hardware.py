import psutil
import os


def get_default_partition_size():
    """Get the size of the default partition where the program is running."""
    current_directory = os.getcwd()
    partition_usage = psutil.disk_usage(current_directory)
    return partition_usage.total


def get_total_memory():
    """Get the total amount of memory (RAM) in bytes."""
    mem_info = psutil.virtual_memory()
    return mem_info.total


def get_dir_size(path="."):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except (OSError, FileNotFoundError):
                # skip files that can't be accessed (e.g. broken symlinks)
                pass
    return total
