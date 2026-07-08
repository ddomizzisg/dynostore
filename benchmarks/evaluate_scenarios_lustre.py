import os
import sys
import time
import subprocess
import json
import random
import uuid
import requests
import argparse

from dynostore.client import Client
from kagio.kagio import KAGIO

# Add benchmarks directory to path so it can find things if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_cmd(cmd, env_vars=None):
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    subprocess.run(cmd, shell=True, env=env, check=True)

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

def clean_system():
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
    
    # Because Docker containers write logs/objects as root, clearing them locally via Python 
    # results in Permission Denied. We use a temporary root Docker container to bypass this.
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    logs_dir = os.path.join(base_dir, "datacontainer", "code", "logs")
    if os.path.exists(logs_dir):
        try:
            run_cmd(f"docker run --rm -v {logs_dir}:/logs alpine sh -c 'rm -rf /logs/*'")
        except Exception as e:
            print(f"Error clearing logs: {e}")
            
    for i in range(1, 11):
        obj_dir = os.path.join(base_dir, "datacontainer", f"objects{i}")
        if os.path.exists(obj_dir):
            try:
                run_cmd(f"docker run --rm -v {obj_dir}:/obj alpine sh -c 'rm -rf /obj/*'")
            except Exception as e:
                print(f"Error clearing objects{i}: {e}")

    # Reset internal metrics database in each container API
    print("Resetting internal metrics via APIGateway...")
    gateway_host = os.getenv("GATEWAY_HOST", "127.0.0.1:8070")
    try:
        requests.post(f"http://{gateway_host}/metrics/reset", timeout=5)
    except Exception as e:
        print(f"Failed to reset metrics: {e}")

def restart_cluster(enable_kagio, enable_replicator, build_containers=False):
    print(f"\n---> Restarting Cluster: KAGIO={enable_kagio}, REPLICATOR={enable_replicator} <---")
    env = {
        "ENABLE_KAGIO": str(enable_kagio).lower(),
        "ENABLE_REPLICATOR": str(enable_replicator).lower()
    }
    # Force recreate apigateway and datacontainers
    build_flag = "--build " if build_containers else ""
    cmd = f"docker compose -f ../docker-compose.lustre.yml up -d {build_flag}--force-recreate apigateway metadata_server datacontainer1 datacontainer2 datacontainer3 datacontainer4 datacontainer5 datacontainer6 datacontainer7 datacontainer8 datacontainer9 datacontainer10"
    run_cmd(cmd, env)
    print("Waiting 15 seconds for services to become healthy...")
    time.sleep(15)

def get_pageranks(kagio_host):
    try:
        KAGIO_API_KEY = os.getenv("KAGIO_API_KEY", "my_token")
        KAGIO_FOXX_URL = os.getenv("KAGIO_FOXX_URL", "http://10.18.173.209:8529/_db/_system/kagio")
        KAGIO_FOXX_DB = os.getenv("KAGIO_FOXX_DB", "_system")
        kagio_client = KAGIO(base_url=kagio_host, foxx_url=KAGIO_FOXX_URL, foxx_db=KAGIO_FOXX_DB, api_key=KAGIO_API_KEY)
        
        pr_list = kagio_client.centrality.data_containers_page_rank()
        
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
    return {}

def collect_metrics(kagio_host):
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
    pageranks = get_pageranks(kagio_host)
    for dc, data in metrics.items():
        data["pagerank"] = pageranks.get(dc, 0.0)
        
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

def run_scenario(scenario_name, enable_kagio, enable_replicator, num_objects=10, benchmark_reads=50, build_containers=False):
    print(f"\n=======================================================")
    print(f" RUNNING SCENARIO: {scenario_name}")
    print(f"=======================================================")
    
    clean_system()
    restart_cluster(enable_kagio, enable_replicator, build_containers)
    
    gateway_host = os.getenv("GATEWAY_HOST", "127.0.0.1:8070")
    kagio_host = os.getenv("KAGIO_HOST", "http://10.18.173.209:8080")
    catalog_name = "eval_catalog"
    client = Client(gateway_host)
    rnd = random.Random(42) # Deterministic workload
    client_regions = ["eu-west", "us-east", "us-west", "ap-south"]
    
    print("\n--- Phase 1: Ingestion & Indegree Generation ---")
    objects = []
    
    write_latencies = []
    read_latencies = []
    failed_writes = 0
    failed_reads = 0
    total_mb_written = 0
    total_mb_read_warmup = 0
    
    t_ingest_start = time.time()    
    for i in range(num_objects):
        region = rnd.choice(client_regions)
        size_MB = rnd.randint(10, 50) # smaller size for faster evals
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

        # Target indegree based on a Pareto distribution (alpha=1.16 for ~80/20 rule)
        # Using a base scale and capping it to avoid infinite test times
        times = int(rnd.paretovariate(1.16) * 5)
        # Ensure at least 1 read and cap at e.g., 200 for practical benchmarking time
        times = max(1, min(times, 200))

        objects.append({
            "id": obj_id,
            "reads": times
        })

        print(f"  -> Performing {times} reads to generate baseline graph...")
        for _ in range(times):
            try:
                t0 = time.time()
                client.get(key=obj_id)
                t1 = time.time()
                read_latencies.append(t1 - t0)
                total_mb_read_warmup += size_MB
                time.sleep(0.05) # Prevent overloading with continuous bursts
            except Exception as e:
                print(f"     Read failed: {e}")
                failed_reads += 1
            
    if enable_replicator:
        wait_time = 45
        print(f"\n--- Phase 2: Waiting {wait_time}s for automatic replication ---")
        time.sleep(wait_time)
    else:
        print("\n--- Phase 2: Replication disabled, skipping wait ---")

    if objects and enable_kagio:
        last_obj = objects[-1]
        wait_for_kagio_sync(kagio_host, last_obj["id"], last_obj["reads"])
    elif not enable_kagio:
        time.sleep(5) # Brief wait if kagio is disabled just in case

    t_ingest_end = time.time()
    ingestion_time = t_ingest_end - t_ingest_start

    print("\n--- Collecting metrics before replication ---")
    metrics_before_repl = collect_metrics(kagio_host)
    replication_time = wait_time if enable_replicator else 0.0

    print("\n--- Collecting PageRanks before benchmark ---")
    pr_before = get_pageranks(kagio_host)

    print("\n--- Phase 3: Benchmark Replicated Objects ---")
    # Identify top 25% objects by intended reads
    top_objects = sorted(objects, key=lambda x: x["reads"], reverse=True)
    top_25_count = max(1, int(len(top_objects) * 0.25))
    top_25 = top_objects[:top_25_count]
    
    print(f"Targeting top {top_25_count} objects...")
    
    benchmark_mb_read = 0
    failed_benchmark_reads = 0
    
    t_start = time.time()
    for idx, obj in enumerate(top_25):
        obj_id = obj["id"]
        print(f"[{idx+1}/{top_25_count}] Benchmarking {obj_id} ({benchmark_reads} reads)...")
        
        for _ in range(benchmark_reads):
            try:
                t0 = time.time()
                client.get(key=obj_id)
                t1 = time.time()
                read_latencies.append(t1 - t0)
                benchmark_mb_read += obj.get("size_MB", 30) # Average size if not saved
            except Exception as e:
                failed_benchmark_reads += 1
            
    t_end = time.time()
    perf_time = round(t_end - t_start, 2)
    print(f"\nBenchmark Performance Time: {perf_time} seconds")
    
    if top_25 and enable_kagio:
        last_bench_obj = top_25[-1]
        # Total expected indegree is baseline reads + benchmark reads
        expected_indegree = last_bench_obj["reads"] + benchmark_reads
        wait_for_kagio_sync(kagio_host, last_bench_obj["id"], expected_indegree)
    elif not enable_kagio:
        time.sleep(5)
    
    print("\n--- Phase 4: Collecting Metrics ---")
    metrics = collect_metrics(kagio_host)
    
    # Calculate PageRank variation and metrics
    requests_list = []
    for dc, data in metrics.items():
        requests_list.append(data.get("requests_attended", 0))
        data["pagerank_before"] = pr_before.get(dc, 0.0)
        data["pagerank_after"] = data.pop("pagerank", 0.0)
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
    args = parser.parse_args()
    
    # Load existing results to update them instead of wiping if only running specific tests
    report_file = "evaluation_report.json"
    existing_results = []
    if os.path.exists(report_file):
        try:
            with open(report_file, 'r') as f:
                existing_results = json.load(f)
        except Exception:
            pass
            
    tests_to_run = [t.strip() for t in args.test.split(',')]
    new_results = []
    
    first_test_executed = False
    def should_build():
        nonlocal first_test_executed
        if args.build and not first_test_executed:
            first_test_executed = True
            return True
        return False
    
    if "all" in tests_to_run or "1" in tests_to_run:
        res = run_scenario("Utilization Factor LB (No Replication)", enable_kagio=False, enable_replicator=False, num_objects=args.num_objects, benchmark_reads=args.benchmark_reads, build_containers=should_build())
        new_results.append(res)
        
    if "all" in tests_to_run or "2" in tests_to_run:
        res = run_scenario("PageRank LB (No Replication)", enable_kagio=True, enable_replicator=False, num_objects=args.num_objects, benchmark_reads=args.benchmark_reads, build_containers=should_build())
        new_results.append(res)
        
    if "all" in tests_to_run or "3" in tests_to_run:
        res = run_scenario("PageRank LB (With Replication)", enable_kagio=True, enable_replicator=True, num_objects=args.num_objects, benchmark_reads=args.benchmark_reads, build_containers=should_build())
        new_results.append(res)
        
    # Merge results
    final_results = []
    for er in existing_results:
        # Keep existing if it wasn't just re-run
        if not any(nr["scenario"] == er["scenario"] for nr in new_results):
            final_results.append(er)
    final_results.extend(new_results)

    print("\n=======================================================")
    print(" EVALUATION COMPLETE")
    print("=======================================================")
    with open(report_file, "w") as f:
        json.dump(final_results, f, indent=2)
    print(f"Report saved to {report_file}")

if __name__ == "__main__":
    main()
