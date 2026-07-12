#!/usr/bin/env python3
"""
Generate a paper-style plot for the Hybrid UF -> PR configuration.

The figure shows:
1. Normalized PageRank share before and after PR-aware routing.
2. Requests attended by each data container.

Usage:
    python plot_hybrid_pagerank.py --input evaluation_report.json

Outputs:
    hybrid_pagerank_redistribution.png
    hybrid_pagerank_redistribution.pdf
    hybrid_pagerank_data.csv
"""

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def container_number(container_name: str) -> int:
    """Extract the numeric suffix from names like 'datacontainer10'."""
    match = re.search(r"(\d+)$", container_name)
    return int(match.group(1)) if match else 0


def find_hybrid_scenario(results):
    """Find the scenario corresponding to the hybrid UF warmup + PR solution."""
    for scenario in results:
        name = scenario.get("scenario", "").lower()
        if "hybrid" in name or ("warmup" in name and "pr" in name):
            return scenario

    available = [scenario.get("scenario", "UNKNOWN") for scenario in results]
    raise ValueError(
        "Could not find the hybrid scenario. Available scenarios are:\n"
        + "\n".join(f"- {name}" for name in available)
    )


def build_dataframe(hybrid_scenario):
    """Convert container metrics into a dataframe."""
    rows = []

    for container, metrics in hybrid_scenario["container_metrics"].items():
        rows.append(
            {
                "container": container,
                "container_id": container_number(container),
                "pagerank_before": metrics["pagerank_before"],
                "pagerank_after": metrics["pagerank_after"],
                "pagerank_variation": metrics["pagerank_variation"],
                "requests_attended": metrics["requests_attended"],
                "objects_count": metrics["objects_count"],
                "storage_MB": metrics["storage_MB"],
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values("container_id").reset_index(drop=True)

    # Normalize PageRank values so the plot shows relative importance.
    # This is usually better for papers because raw PageRank values can change scale.
    df["pagerank_before_share"] = df["pagerank_before"] / df["pagerank_before"].sum()
    df["pagerank_after_share"] = df["pagerank_after"] / df["pagerank_after"].sum()

    df["pagerank_share_change"] = (
        df["pagerank_after_share"] - df["pagerank_before_share"]
    )

    df["pagerank_share_change_percent"] = 100 * df["pagerank_share_change"]

    return df


def make_plot(df, scenario_name, output_base):
    """Generate and save the plot."""
    x = range(len(df))
    labels = [f"DC{n}" for n in df["container_id"]]

    fig, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(10, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.2]},
    )

    ax1, ax2 = axes

    # -----------------------------
    # Panel A: PageRank before/after
    # -----------------------------
    ax1.plot(
        x,
        df["pagerank_before_share"] * 100,
        marker="o",
        linewidth=2,
        label="After UF warmup",
    )

    ax1.plot(
        x,
        df["pagerank_after_share"] * 100,
        marker="s",
        linewidth=2,
        label="After PR-aware routing",
    )

    # Add light connector lines between before and after values.
    for i, row in df.iterrows():
        ax1.plot(
            [i, i],
            [
                row["pagerank_before_share"] * 100,
                row["pagerank_after_share"] * 100,
            ],
            linewidth=1,
            alpha=0.35,
        )

    ax1.set_ylabel("Normalized PageRank share (%)")
    ax1.set_title("Hybrid UF → PR: PageRank redistribution across containers")
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    ax1.legend(frameon=False)

    # ---------------------------------
    # Panel B: Requests per data node
    # ---------------------------------
    ax2.bar(
        x,
        df["requests_attended"],
        label="Requests attended",
    )

    mean_requests = df["requests_attended"].mean()
    ax2.axhline(
        mean_requests,
        linestyle="--",
        linewidth=1.5,
        label=f"Mean requests = {mean_requests:.1f}",
    )

    ax2.set_ylabel("Requests")
    ax2.set_xlabel("Data container")
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    ax2.legend(frameon=False)

    # Highlight the most loaded container.
    max_idx = df["requests_attended"].idxmax()
    max_container = labels[max_idx]
    max_requests = df.loc[max_idx, "requests_attended"]

    ax2.annotate(
        f"Max: {max_container}\n{max_requests} requests",
        xy=(max_idx, max_requests),
        xytext=(max_idx, max_requests * 1.08),
        ha="center",
        arrowprops={"arrowstyle": "->", "linewidth": 1},
    )

    fig.suptitle(scenario_name, y=0.98, fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    png_path = f"{output_base}.png"
    pdf_path = f"{output_base}.pdf"

    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")

    print(f"Saved: {png_path}")
    print(f"Saved: {pdf_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="evaluation_report.json",
        help="Path to evaluation_report.json",
    )
    parser.add_argument(
        "--output-base",
        default="hybrid_pagerank_redistribution",
        help="Base name for output files, without extension",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(f"Could not find input file: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        results = json.load(f)

    hybrid_scenario = find_hybrid_scenario(results)
    df = build_dataframe(hybrid_scenario)

    # Save the processed data used in the figure.
    csv_path = f"{args.output_base}_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"Saved: {csv_path}")

    make_plot(
        df=df,
        scenario_name=hybrid_scenario["scenario"],
        output_base=args.output_base,
    )


if __name__ == "__main__":
    main()
