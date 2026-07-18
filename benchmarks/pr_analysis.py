import json

file = "/home/domizzi/Documents/GitHub/dynostore/benchmarks/evaluation_report.json"
with open(file, 'r') as f:
    data = json.load(f)
    scenario = data[1] # Hybrid
    metrics = scenario['container_metrics']
    print(f"Container PR analysis for {file}:")
    print(f"{'Container':<15} | {'Objects':<8} | {'Requests After':<15} | {'PR Before':<10} | {'PR After':<10}")
    print("-" * 65)
    for k, v in sorted(metrics.items(), key=lambda x: int(x[0].replace('datacontainer', ''))):
        print(f"{k:<15} | {v['objects_count']:<8} | {v['requests_after_replication']:<15} | {v['pagerank_before']:.6f}   | {v['pagerank_after']:.6f}")
