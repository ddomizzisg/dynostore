import json
import numpy as np

def summarize(file):
    print(f"=====================================")
    print(f"Summary for {file.split('/')[-1]}")
    print(f"=====================================")
    with open(file, 'r') as f:
        data = json.load(f)
        for i, scenario in enumerate(data):
            print(f"Scenario {i}: {scenario.get('scenario', 'Unknown')}")
            print(f"  Performance Time: {scenario.get('performance_time_seconds')} s")
            
            if 'throughput' in scenario:
                print(f"  Read Throughput: {scenario['throughput'].get('read_throughput_mb_s')} MB/s")
                print(f"  Write Throughput: {scenario['throughput'].get('write_throughput_mb_s')} MB/s")
            
            if 'cluster_stats' in scenario:
                cs = scenario['cluster_stats']
                print(f"  Cluster Stats - Max Requests: {cs.get('max_requests_attended')}, Mean: {cs.get('mean_requests_attended')}, Fairness: {cs.get('jains_fairness_index')}")
                
            if 'user_latencies' in scenario:
                write_lats = scenario['user_latencies'].get('write_latencies_seconds', [])
                read_lats = scenario['user_latencies'].get('read_latencies_seconds', [])
                if write_lats:
                    print(f"  Write Latency - Mean: {np.mean(write_lats):.4f}s, Max: {np.max(write_lats):.4f}s, p99: {np.percentile(write_lats, 99):.4f}s")
                if read_lats:
                    print(f"  Read Latency  - Mean: {np.mean(read_lats):.4f}s, Max: {np.max(read_lats):.4f}s, p99: {np.percentile(read_lats, 99):.4f}s")
            print("-" * 40)
            
summarize("/home/domizzi/Documents/GitHub/dynostore/benchmarks/evaluation_report.json")
summarize("/home/domizzi/Documents/GitHub/dynostore/benchmarks/t1.json")
