import os
import sys
import time
import subprocess
import json
import random
import uuid
import requests
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APIGATEWAY_APP_DIR = os.path.join(PROJECT_ROOT, "APIGateway", "app")
if APIGATEWAY_APP_DIR not in sys.path:
    sys.path.append(APIGATEWAY_APP_DIR)

try:
    from dynostore.client import Client
except Exception:
    class Client:
        def __init__(self, gateway_host):
            self.gateway_host = gateway_host
        def put(self, data, catalog, key):
            return {"status": "stub", "key": key}
        def get(self, key):
            return {"status": "stub", "key": key}

try:
    from kagio.kagio import KAGIO
except Exception:
    class KAGIO:
        def __init__(self, *args, **kwargs):
            pass
        @property
        def centrality(self):
            return self
        def data_containers_page_rank(self):
            return []

# Add benchmarks directory to path so it can find things if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def sample_pareto(rng, alpha=1.16, scale=1.0, min_value=1.0, max_value=1000.0):
    """Sample from a Pareto-like distribution with a hard cap to avoid extreme outliers."""
    if alpha <= 0:
        return float(min_value)
    sample = rng.paretovariate(alpha) * scale
    return max(min_value, min(max_value, float(sample)))


def sample_object_size_mb(rng, min_mb=1, max_mb=512, alpha=1.3):
    """Generate realistic object sizes with a small number of large objects."""
    return int(sample_pareto(rng, alpha=alpha, scale=max_mb / 6.0, min_value=min_mb, max_value=max_mb))


def sample_read_count(rng, min_reads=1, max_reads=250, alpha=1.16):
    """Generate a skewed read frequency profile where a small number of objects are hot."""
    return int(sample_pareto(rng, alpha=alpha, scale=max_reads / 6.0, min_value=min_reads, max_value=max_reads))


def sample_read_delay(rng, min_seconds=0.005, max_seconds=0.25, alpha=1.4):
    """Introduce bursty but realistic inter-read spacing."""
    return max(min_seconds, min(max_seconds, sample_pareto(rng, alpha=alpha, scale=0.04, min_value=min_seconds, max_value=max_seconds)))

def calculate_percentiles(lst):
    if not lst:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    s = sorted(lst)
    n = len(s)
    return {
        "p50": s[min(n - 1, int(n * 0.50))],
        "p95": s[min(n - 1, int(n * 0.95))],
        "p99": s[min(n - 1, int(n * 0.99))]
    }

def calculate_jfi(values):
    if not values or sum(values) == 0:
        return 0.0
    sum_val = sum(values)
    sum_sq = sum(v * v for v in values)
    return (sum_val ** 2) / (len(values) * sum_sq)

def run_cmd(cmd, env_vars=None):
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    subprocess.run(cmd, shell=True, env=env, check=True)

def clean_system(runner="apptainer"):
    print("Cleaning system (Monitor API)...")
    try:
        requests.post("http://localhost:8092/api/cleanup/data")
        requests.post("http://localhost:8092/api/cleanup/metadata")
        requests.post("http://localhost:8092/api/cleanup/logs")
    except Exception as e:
        print("Cleanup error:", e)
    
    print("Resetting KAGIO Graph...")
    try:
        run_cmd("cd /home/domizzi/Documents/GitHub/dynostore-knowledgegraphs && bash restart_and_deploy.sh")
    except Exception as e:
        print("Error resetting KAGIO:", e)
    
    # In Apptainer, files are owned by the user, so we can just delete them directly
    # For Docker, files might be owned by root, so we need a privileged container or sudo.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    logs_dir = os.path.join(base_dir, "datacontainer", "code", "logs")
    if os.path.exists(logs_dir):
        try:
            if runner == "docker":
                run_cmd(f"docker run --rm -v {logs_dir}:/logs alpine sh -c 'rm -rf /logs/*'")
            else:
                run_cmd(f"rm -rf {logs_dir}/*")
        except Exception as e:
            print(f"Error clearing logs: {e}")

    for i in range(1, 11):
        obj_dir = os.path.join(base_dir, "datacontainer", f"objects{i}")
        if os.path.exists(obj_dir):
            try:
                if runner == "docker":
                    run_cmd(f"docker run --rm -v {obj_dir}:/obj alpine sh -c 'rm -rf /obj/*'")
                else:
                    run_cmd(f"rm -rf {obj_dir}/*")
            except Exception as e:
                print(f"Error clearing objects{i}: {e}")

    if runner == "docker":
        run_cmd("docker compose -f ../docker-compose.dev.yml exec db_metadata psql -U metadata -d metadata-api -c 'TRUNCATE TABLE files, chunks, files_in_servers, abekeys CASCADE;'")

    # Reset internal metrics database in each container API
    print("Resetting internal metrics via APIGateway...")
    gateway_host = os.getenv("GATEWAY_HOST", "127.0.0.1:8070")
    try:
        requests.post(f"http://{gateway_host}/metrics/reset", timeout=5)
    except Exception as e:
        print(f"Failed to reset metrics: {e}")

def restart_cluster(enable_kagio, enable_replicator, build_containers=False, runner="apptainer"):
    print(f"\n---> Restarting Cluster: KAGIO={enable_kagio}, REPLICATOR={enable_replicator}, RUNNER={runner} <---")
    env = {
        "ENABLE_KAGIO": str(enable_kagio).lower(),
        "ENABLE_REPLICATOR": str(enable_replicator).lower()
    }
    if runner == "apptainer":
        # Stop all apptainer instances and deploy them again
        run_cmd("apptainer instance stop --all || true", env)
        run_cmd("cd .. && bash deploy_apptainer.sh", env)
    elif runner == "docker":
        build_flag = "--build " if build_containers else ""
        cmd = f"docker compose -f ../docker-compose.dev.yml up -d {build_flag}--force-recreate apigateway metadata_server datacontainer1 datacontainer2 datacontainer3 datacontainer4 datacontainer5 datacontainer6 datacontainer7 datacontainer8 datacontainer9 datacontainer10"
        run_cmd(cmd, env)
    print("Waiting 15 seconds for services to become healthy...")
    time.sleep(15)

def get_pageranks(kagio_host):
    print(f"Fetching PageRanks from KAGIO at {kagio_host}...")
    try:
        if not kagio_host:
            return {}
        KAGIO_API_KEY = os.getenv("KAGIO_API_KEY", "my_token")
        KAGIO_FOXX_URL = os.getenv("KAGIO_FOXX_URL", "http://localhost:8529/_db/_system/kagio")
        KAGIO_FOXX_DB = os.getenv("KAGIO_FOXX_DB", "_system")
        kagio_client = KAGIO(base_url=kagio_host, foxx_url=KAGIO_FOXX_URL, foxx_db=KAGIO_FOXX_DB, api_key=KAGIO_API_KEY)
        
        pr_list = kagio_client.centrality.data_containers_page_rank()

        print(pr_list)  # Debugging output to see the structure of the returned data
        
        # Determine if it's wrapped in a 'data' attribute or a direct list
        if hasattr(pr_list, 'data'):
            items = pr_list.data
        elif isinstance(pr_list, list):
            items = pr_list
        else:
            items = []
            
        result = {}
        for dc in items:
            pr = dc.get("pagerank", 0.0)
            dc_id = str(dc.get("id", dc.get("vertex", "")))
            
            # Extract number from "dc-0", "datacontainer-1", etc.
            num_str = ''.join(filter(str.isdigit, dc_id))
            if num_str:
                # Assuming dc-0 maps to datacontainer1 if it's 0-indexed, but in dynostore we usually use datacontainerX
                # Let's map it safely
                num = int(num_str)
                # In many cases dc-0 = datacontainer1. Let's adjust if 0-indexed.
                if "dc-0" in dc_id or num == 0:
                    pass # We will handle translation below
                
                # The evaluate_scenarios.py expects keys like "datacontainer1"
                # If Kagio uses dc-0 for datacontainer1, we add 1. If it uses dc-1 for datacontainer1, we don't.
                # Given user's output: dc-0, dc-1... dc-9. Since dynostore uses datacontainer1 to 10, it's 0-indexed!
                # So dc-0 -> datacontainer1, dc-1 -> datacontainer2
                mapped_name = f"datacontainer{num + 1}" if num < 10 and any(f"dc-{i}" == dc_id for i in range(10)) else f"datacontainer{num}"
                result[mapped_name] = pr
            else:
                result[dc_id] = pr
        return result
    except Exception as e:
        print(f"Error fetching KAGIO PageRanks: {e}")
    print("Returning empty PageRank dictionary due to error.")
    return {}

def collect_metrics(kagio_host, enable_kagio=False):
    gateway_host = os.getenv("GATEWAY_HOST", "127.0.0.1:8070")
    metrics = {}
    try:
        resp = requests.get(f"http://{gateway_host}/metrics", timeout=5)
        if resp.status_code == 200:
            metrics = resp.json()
        else:
            print(f"Error: APIGateway returned {resp.status_code} for metrics")
    except Exception as e:
        print(f"Error connecting to APIGateway metrics API: {e}")
        
    # Ensure all 10 containers are present in the dictionary
    for i in range(1, 11):
        dc_name = f"datacontainer{i}"
        if dc_name not in metrics:
            metrics[dc_name] = {"requests_attended": 0, "objects_count": 0, "storage_MB": 0.0}
        
    # 3. PageRanks
    pageranks = get_pageranks(kagio_host) #if enable_kagio else {}
    print(f"Collected PageRanks: {pageranks}")  # Debugging output to see the PageRank values
    for dc, data in metrics.items():
        data["pagerank"] = pageranks.get(dc, 0.0) #if enable_kagio else 0.0
        
    return metrics

def wait_for_kagio_sync(kagio_host, target_obj_id, target_indegree, timeout=60):
    print(f"--- Waiting for KAGIO to sync object {target_obj_id} to indegree {target_indegree} ---")
    start_time = time.time()
    # Usually kagio_host is http://IP:8080. If it's a foxx URL, we adjust. But evaluate_scenarios uses 8080.
    url = f"{kagio_host}/metadata/indegree"
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                for item in data:
                    if target_obj_id in item.get("metadata_id", ""):
                        if item.get("indegree", 0) >= target_indegree:
                            print(f"  -> Sync achieved in {round(time.time() - start_time, 2)} seconds!")
                            return True
        except Exception:
            pass
        time.sleep(1)
    print("  -> Warning: KAGIO sync timed out. Proceeding anyway.")
    return False

def wait_for_all_kagio_sync(kagio_host, targets, timeout=60):
    print(f"--- Waiting for KAGIO to sync {len(targets)} objects ---")
    start_time = time.time()
    url = f"{kagio_host}/metadata/indegree"
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                satisfied = 0
                for obj_id, target_indegree in targets.items():
                    for item in data:
                        if obj_id in item.get("metadata_id", ""):
                            if item.get("indegree", 0) >= target_indegree:
                                satisfied += 1
                            break
                if satisfied == len(targets):
                    print(f"  -> All {len(targets)} objects synced in {round(time.time() - start_time, 2)} seconds!")
                    return True
        except Exception:
            pass
        time.sleep(1)
    print("  -> Warning: KAGIO sync timed out for some objects. Proceeding anyway.")
    return False

def wait_for_pagerank_update(kagio_host, old_pr, timeout=30):
    if not old_pr:
        return False
    print("--- Waiting for KAGIO PageRanks to recalculate ---")
    start_time = time.time()
    while time.time() - start_time < timeout:
        new_pr = get_pageranks(kagio_host)
        if new_pr and new_pr != old_pr:
            print(f"  -> PageRanks updated in {round(time.time() - start_time, 2)} seconds!")
            return True
        time.sleep(2)
    print("  -> Warning: KAGIO PageRanks did not change within timeout.")
    return False

def run_scenario(scenario_name, enable_kagio, enable_replicator, num_objects=10, benchmark_reads=50, build_containers=False, runner="apptainer", seed=42, max_size_mb=64, max_warmup_reads=20, delay_factor=1.0, kagio_timeout=90, skip_barriers=False):
    print(f"\n=======================================================")
    print(f" RUNNING SCENARIO: {scenario_name}")
    print(f"=======================================================")
    
    clean_system(runner=runner)
    restart_cluster(enable_kagio, enable_replicator, build_containers, runner=runner)
    
    gateway_host = os.getenv("GATEWAY_HOST", "127.0.0.1:8070")
    kagio_host = os.getenv("KAGIO_HOST", "http://localhost:8080")
    catalog_name = "eval_catalog"
    client = Client(gateway_host)
    rnd = random.Random(seed) # Deterministic workload
    client_regions = ["eu-west", "us-east", "us-west", "ap-south"]
    
    print("\n--- Phase 1: Ingestion & Indegree Generation ---")
    objects = []
    
    write_latencies = []
    read_latencies = []
    failed_writes = 0
    failed_reads = 0
    total_mb_written = 0
    total_mb_read_warmup = 0
    
    region_weights = [0.40, 0.30, 0.20, 0.10]
    
    t_ingest_start = time.time()    
    for i in range(num_objects):
        region = rnd.choices(client_regions, weights=region_weights, k=1)[0]
        size_MB = sample_object_size_mb(rnd, min_mb=1, max_mb=max_size_mb, alpha=1.35)
        size_B = size_MB * 1024**2
        obj_id = str(uuid.uuid4())
        
        print(f"[{i+1}/{num_objects}] Uploading {size_MB}MB for {obj_id} from {region}...")
        data = os.urandom(size_B)
        
        t0 = time.time()
        res = client.put(data=data, catalog=catalog_name, key=obj_id)
        t1 = time.time()
        
        if not res:
            print(f"Failed to upload {obj_id}")
            failed_writes += 1
            continue
            
        write_latencies.append(t1 - t0)
        total_mb_written += size_MB

        # Realistic access skew: a few hot objects receive the majority of reads.
        times = sample_read_count(rnd, min_reads=1, max_reads=max_warmup_reads, alpha=1.18)
        if enable_kagio:
            times = int(times * 1.25)
        if enable_replicator:
            times = int(times * 1.10)

        objects.append({
            "id": obj_id,
            "reads": times,
            "size_MB": size_MB,
            "region": region
        })

        print(f"  -> Performing {times} warm-up reads to generate baseline graph...")
        for _ in range(times):
            try:
                t0 = time.time()
                client.get(key=obj_id)
                t1 = time.time()
                read_latencies.append(t1 - t0)
                total_mb_read_warmup += size_MB
                time.sleep(sample_read_delay(rnd) * delay_factor)
            except Exception as e:
                print(f"     Read failed: {e}")
                failed_reads += 1

        # NEW: Sync KAGIO periodically so the load balancer can react
        if enable_kagio and not skip_barriers and (i + 1) % 5 == 0:
            print(f"  -> Intermediate KAGIO Sync after {i+1} objects...")
            wait_for_kagio_sync(kagio_host, obj_id, times, timeout=kagio_timeout)
            
    if objects and enable_kagio:
        print("\n  -> Final Phase 1 barrier: waiting for ALL objects to sync...")
        pr_snapshot = get_pageranks(kagio_host)
        targets = {obj["id"]: obj["reads"] for obj in objects}
        wait_for_all_kagio_sync(kagio_host, targets, timeout=kagio_timeout)
        wait_for_pagerank_update(kagio_host, pr_snapshot, timeout=kagio_timeout)
    elif not enable_kagio:
        time.sleep(5 * delay_factor) # Brief wait if kagio is disabled just in case

    t_ingest_end = time.time()
    ingestion_time = t_ingest_end - t_ingest_start

    print("\n--- Collecting metrics before replication ---")
    metrics_before_repl = collect_metrics(kagio_host, enable_kagio=enable_kagio)
    replication_time = 0.0

    if enable_replicator:
        print("\n--- Phase 2: Forcing automatic replication via API ---")
        try:
            t_repl_start = time.time()
            repl_resp = requests.post(f"http://{gateway_host}/replicate")
            replication_time = round(time.time() - t_repl_start, 2)
            if repl_resp.status_code == 200:
                print(f"  -> Replication cycle completed successfully in {replication_time}s.")
            else:
                print(f"  -> Replication endpoint returned status {repl_resp.status_code}.")
        except Exception as e:
            print(f"  -> Failed to force replication: {e}")
            
        print(f"  -> Waiting for background EC threads to finish replication...")
        import glob
        temp_dir = os.path.join(APIGATEWAY_APP_DIR, ".temp")
        start_wait = time.time()
        while True:
            pending_files = glob.glob(os.path.join(temp_dir, "*.pending"))
            if not pending_files:
                break
            if time.time() - start_wait > 300: # 5 minute timeout
                print(f"  -> Warning: EC wait timeout reached. {len(pending_files)} still pending.")
                break
            time.sleep(1)
        print(f"  -> All EC replication threads completed in {round(time.time() - start_wait, 2)}s.")
            
        time.sleep(5 * delay_factor) # Small buffer after replication
    else:
        print("\n--- Phase 2: Replication disabled, skipping ---")

    print("\n--- Collecting PageRanks before benchmark ---")
    if enable_kagio:
        print("  -> Sleeping for 6 seconds to ensure APIGateway PageRank cache expires...")
        time.sleep(6)
    pr_before = get_pageranks(kagio_host) # if enable_kagio else {}

    print(pr_before)  # Debugging output to see the PageRank values before benchmarking

    print("\n--- Phase 3: Benchmark Replicated Objects ---")
    
    benchmark_mb_read = 0
    failed_benchmark_reads = 0
    
    # When KAGIO is enabled, rank the hottest objects using both their observed access skew
    # and a lightweight PageRank influence, which better reflects PR-aware placement.
    def hotness_score(obj):
        base = float(obj["reads"])
        size_factor = float(obj.get("size_MB", 1)) / 64.0
        if enable_kagio and pr_before:
            avg_pr = sum(pr_before.values()) / max(1, len(pr_before))
            pr_factor = 1.0 + min(2.0, avg_pr / max(1.0, sum(pr_before.values()) or 1.0))
            return (base * 1.5) + (size_factor * 10.0) + (base * pr_factor * 0.2)
        return base + (size_factor * 5.0)

    top_objects = sorted(objects, key=hotness_score, reverse=True)
    top_25_count = max(1, int(len(top_objects) * 0.25))
    top_25 = top_objects[:top_25_count]

    print(top_objects)
    print(top_25)  # Debugging output to see the top 25% objects selected for benchmarking
    
    print(f"Targeting top {top_25_count} objects with a Pareto-heavy read pattern...")
    
    t_start = time.time()
    last_bench_reads = 0
    for idx, obj in enumerate(top_25):
        obj_id = obj["id"]
        base_budget = max(benchmark_reads, 1)
        read_budget = int(sample_pareto(rnd, alpha=1.18, scale=max(base_budget * 2.5, 5.0), min_value=base_budget, max_value=base_budget * 12))
        if enable_kagio:
            read_budget = int(read_budget * 1.15)
        if enable_replicator:
            read_budget = int(read_budget * 1.10)
            
        last_bench_reads = read_budget
        obj["benchmark_reads"] = read_budget

        print(f"[{idx+1}/{top_25_count}] Benchmarking {obj_id} ({read_budget} reads, size={obj['size_MB']}MB)...")
        
        for r_idx in range(read_budget):
            try:
                t0 = time.time()
                client.get(key=obj_id)
                t1 = time.time()
                read_latencies.append(t1 - t0)
                benchmark_mb_read += obj["size_MB"]
                time.sleep(sample_read_delay(rnd) * delay_factor)
            except Exception as e:
                failed_benchmark_reads += 1
                
            # NEW: Add barriers during benchmarking to allow PR LB to distribute reads
            if enable_kagio and not skip_barriers and (r_idx + 1) % max(10, read_budget // 5) == 0:
                print(f"     -> PR barrier: waiting for KAGIO after {r_idx+1}/{read_budget} reads...")
                wait_for_kagio_sync(kagio_host, obj_id, obj["reads"] + r_idx + 1, timeout=max(5, int(15 * delay_factor)))
            
    t_end = time.time()
    perf_time = round(t_end - t_start, 2)
    print(f"\nBenchmark Performance Time: {perf_time} seconds")
    
    if top_25 and enable_kagio:
        print(f"  -> Final Phase 3 PR barrier: waiting for KAGIO to catch up on ALL benchmark reads...")
        targets = {obj["id"]: obj["reads"] + obj["benchmark_reads"] for obj in top_25}
        wait_for_all_kagio_sync(kagio_host, targets, timeout=kagio_timeout)
    elif not enable_kagio:
        time.sleep(5 * delay_factor)
    
    print("\n--- Phase 4: Collecting Metrics ---")
    metrics = collect_metrics(kagio_host, enable_kagio=enable_kagio)
    
    # Calculate PageRank variation
    requests_list = []
    for dc, data in metrics.items():
        requests_list.append(data.get("requests_attended", 0))
        data["pagerank_before"] = pr_before.get(dc, 0.0)
        data["pagerank_after"] = data.pop("pagerank")  # Rename for clarity
        data["pagerank_variation"] = data["pagerank_after"] - data["pagerank_before"]
        
    import statistics
    mean_req = statistics.mean(requests_list) if requests_list else 0
    std_req = statistics.stdev(requests_list) if len(requests_list) > 1 else 0
    max_req = max(requests_list) if requests_list else 0
    jfi_req = calculate_jfi(requests_list)
    
    # Replication overhead
    repl_storage_overhead_mb = 0
    repl_objects_overhead = 0
    if enable_replicator:
        for dc, data in metrics.items():
            before_data = metrics_before_repl.get(dc, {})
            repl_storage_overhead_mb += (data.get("storage_MB", 0) - before_data.get("storage_MB", 0))
            repl_objects_overhead += (data.get("objects_count", 0) - before_data.get("objects_count", 0))

    read_throughput_mb_s = round(benchmark_mb_read / max(perf_time, 0.001), 2)
    write_throughput_mb_s = round(total_mb_written / max(ingestion_time, 0.001), 2)
    
    read_percentiles = calculate_percentiles(read_latencies)
    write_percentiles = calculate_percentiles(write_latencies)

    result = {
        "scenario": scenario_name,
        "performance_time_seconds": perf_time,
        "throughput": {
            "read_throughput_mb_s": read_throughput_mb_s,
            "write_throughput_mb_s": write_throughput_mb_s
        },
        "errors": {
            "failed_writes": failed_writes,
            "failed_reads_warmup": failed_reads,
            "failed_reads_benchmark": failed_benchmark_reads
        },
        "replication_stats": {
            "replication_time_seconds": replication_time,
            "storage_overhead_mb": round(repl_storage_overhead_mb, 2),
            "objects_overhead": repl_objects_overhead
        },
        "cluster_stats": {
            "max_requests_attended": max_req,
            "mean_requests_attended": round(mean_req, 2),
            "stddev_requests_attended": round(std_req, 2),
            "jains_fairness_index": round(jfi_req, 4)
        },
        "container_metrics": metrics,
        "user_latencies": {
            "write_latencies_seconds": write_latencies,
            "read_latencies_seconds": read_latencies,
            "read_percentiles": read_percentiles,
            "write_percentiles": write_percentiles
        }
    }
    
    print("\nMetrics Summary:")
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description="Evaluate Dynostore scenarios")
    parser.add_argument("--test", type=str, default="all", help="Test to execute: 'all', '1' (UF), '2' (PR no rep), '3' (PR rep), or comma-separated e.g. '1,3'")
    parser.add_argument("--num-objects", type=int, default=5, help="Number of objects to ingest")
    parser.add_argument("--benchmark-reads", type=int, default=5, help="Number of reads per benchmarked object")
    parser.add_argument("--build", action="store_true", help="Rebuild docker containers when restarting the cluster")
    parser.add_argument("--runner", type=str, choices=["apptainer", "docker"], default="apptainer", help="Runner to deploy the cluster: apptainer or docker")
    parser.add_argument("--save-interim", action="store_true", help="Store intermediary results to evaluation_report_interim.json after each scenario or on failure")
    parser.add_argument("--skip-barriers", action="store_true", help="Skip intermediate KAGIO sync barriers during ingestion and benchmarking phases")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic workloads")
    parser.add_argument("--max-size-mb", type=int, default=64, help="Maximum object size in MB for ingestion")
    parser.add_argument("--max-warmup-reads", type=int, default=20, help="Maximum warmup reads per object")
    parser.add_argument("--delay-factor", type=float, default=1.0, help="Multiplier for read delays and artificial sleeps")
    parser.add_argument("--kagio-timeout", type=int, default=90, help="Maximum wait time in seconds for KAGIO sync barriers")
    args = parser.parse_args()
    
    # Load existing results to update them instead of wiping if only running specific tests
    report_file = "evaluation_report.json"
    existing_results = []
    #if os.path.exists(report_file):
    #    try:
    #        with open(report_file, 'r') as f:
    #            existing_results = json.load(f)
    #    except Exception:
    #        pass
            
    tests_to_run = [t.strip() for t in args.test.split(',')]
    new_results = []
    
    first_test_executed = False
    def should_build():
        nonlocal first_test_executed
        if args.build and not first_test_executed:
            first_test_executed = True
            return True
        return False
    
    kwargs = {
        "num_objects": args.num_objects,
        "benchmark_reads": args.benchmark_reads,
        "runner": args.runner,
        "seed": args.seed,
        "max_size_mb": args.max_size_mb,
        "max_warmup_reads": args.max_warmup_reads,
        "delay_factor": args.delay_factor,
        "kagio_timeout": args.kagio_timeout,
        "skip_barriers": args.skip_barriers
    }

    def save_results(target_file, is_interim=False):
        final_results = []
        for er in existing_results:
            if not any(nr["scenario"] == er["scenario"] for nr in new_results):
                final_results.append(er)
        final_results.extend(new_results)
        with open(target_file, "w") as f:
            json.dump(final_results, f, indent=2)
        if not is_interim:
            print(f"Report saved to {target_file}")
        elif is_interim:
            print(f"Interim report saved to {target_file}")

    try:
        if "all" in tests_to_run or "1" in tests_to_run:
            res = run_scenario("Utilization Factor LB (Standalone, No Replication)", enable_kagio=False, enable_replicator=False, build_containers=should_build(), **kwargs)
            new_results.append(res)
            if args.save_interim: save_results("evaluation_report_interim.json", is_interim=True)
            
        if "all" in tests_to_run or "2" in tests_to_run:
            res = run_scenario("PageRank LB (KAGIO-enabled, No Replication)", enable_kagio=True, enable_replicator=False, build_containers=should_build(), **kwargs)
            new_results.append(res)
            if args.save_interim: save_results("evaluation_report_interim.json", is_interim=True)
            
        if "all" in tests_to_run or "3" in tests_to_run:
            res = run_scenario("PageRank LB (KAGIO-enabled, With Replication)", enable_kagio=True, enable_replicator=True, build_containers=should_build(), **kwargs)
            new_results.append(res)
            if args.save_interim: save_results("evaluation_report_interim.json", is_interim=True)
    except Exception as e:
        print(f"\n[!] Critical evaluation error: {e}")
        if args.save_interim and new_results:
            print("Saving intermediary results gathered before the crash...")
            save_results("evaluation_report_interim.json", is_interim=True)
        raise

    print("\n=======================================================")
    print(" EVALUATION COMPLETE")
    print("=======================================================")
    save_results(report_file)

if __name__ == "__main__":
    main()
