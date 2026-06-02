from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


TARGET_ALGORITHMS = ["astar", "dijkstra", "bellman-ford", "bfs"]
NON_BFS_ALGORITHMS = ["astar", "dijkstra", "bellman-ford"]
STYLE_MAP = {
    "astar": {"color": "#1f77b4", "linestyle": "-", "marker": "o", "label": "A*"},
    "dijkstra": {"color": "#ff7f0e", "linestyle": "--", "marker": "s", "label": "Dijkstra"},
    "bellman-ford": {"color": "#2ca02c", "linestyle": ":", "marker": "^", "label": "Bellman-Ford"},
    "bfs": {"color": "#d62728", "linestyle": "-.", "marker": "D", "label": "BFS"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate mesh throughput plots")
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "data" / "mesh_throughput.csv")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "mesh")
    return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(csv_path)
    expected = {"algorithm", "second", "bits_per_second", "hop_count"}
    missing = expected.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {', '.join(sorted(missing))}")

    frame = frame.copy()
    frame["algorithm"] = frame["algorithm"].astype(str).str.strip().str.lower()
    frame = frame[frame["algorithm"].isin(TARGET_ALGORITHMS)]

    frame["second"] = pd.to_numeric(frame["second"], errors="coerce")
    frame["bits_per_second"] = pd.to_numeric(frame["bits_per_second"], errors="coerce")
    frame["hop_count"] = pd.to_numeric(frame["hop_count"], errors="coerce")
    frame = frame.dropna(subset=["second", "bits_per_second", "hop_count"])

    frame["throughput_mbps"] = frame["bits_per_second"] / 1_000_000.0
    frame = frame.sort_values(["algorithm", "second"])
    return frame


def save_line_all(frame: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    for algorithm in TARGET_ALGORITHMS:
        algo_frame = frame[frame["algorithm"] == algorithm]
        if algo_frame.empty:
            continue
        style = STYLE_MAP[algorithm]
        ax.plot(algo_frame["second"], algo_frame["throughput_mbps"], label=style["label"], color=style["color"], linestyle=style["linestyle"], marker=style["marker"], linewidth=2.1, markersize=4.2)

    ax.set_title("Throughput Over Time - All Algorithms", fontsize=14, fontweight="bold")
    ax.set_xlabel("Second")
    ax.set_ylabel("Throughput (Mbps)")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()
    fig.subplots_adjust(right=0.78)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_line_non_bfs(frame: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 6.4))
    for algorithm in NON_BFS_ALGORITHMS:
        algo_frame = frame[frame["algorithm"] == algorithm]
        if algo_frame.empty:
            continue
        style = STYLE_MAP[algorithm]
        ax.plot(algo_frame["second"], algo_frame["throughput_mbps"], label=style["label"], color=style["color"], linestyle=style["linestyle"], marker=style["marker"], linewidth=2.1, markersize=4.2)

    ax.set_title("Throughput Over Time - A*, Dijkstra, Bellman-Ford", fontsize=14, fontweight="bold")
    ax.set_xlabel("Second")
    ax.set_ylabel("Throughput (Mbps)")
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0))
    fig.tight_layout()
    fig.subplots_adjust(right=0.78)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def save_box_plot(frame: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    order = TARGET_ALGORITHMS
    palette = {alg: STYLE_MAP[alg]["color"] for alg in order}
    sns.boxplot(x="algorithm", y="throughput_mbps", data=frame, order=order, palette=palette, ax=ax, showmeans=True)
    ax.set_title("Throughput Distribution - Box Plot", fontsize=14, fontweight="bold")
    ax.set_ylabel("Throughput (Mbps)")
    ax.set_xlabel("")
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    plt.setp(ax.get_xticklabels(), rotation=8, ha="right")
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)

def save_kde_plot(frame: pd.DataFrame, output_path: Path) -> None:
	fig, ax = plt.subplots(figsize=(12.0, 6.4))

	for algorithm in TARGET_ALGORITHMS:
		values = frame.loc[frame["algorithm"] == algorithm, "throughput_mbps"]
		if values.empty:
			continue
		style = STYLE_MAP[algorithm]
		sns.kdeplot(
			data=values,
			color=style["color"],
			linestyle=style["linestyle"],
			linewidth=2.3,
			fill=True,
			alpha=0.14,
			bw_adjust=1.0,
			label=style["label"],
			ax=ax,
		)

	ax.set_title("Throughput Distribution - KDE Plot", fontsize=14, fontweight="bold")
	ax.set_xlabel("Throughput (Mbps)", fontsize=11)
	ax.set_ylabel("Density", fontsize=11)
	ax.grid(True, axis="both", linestyle="--", linewidth=0.7, alpha=0.3)
	ax.set_axisbelow(True)
	ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True, title="Algorithm")
	fig.tight_layout()
	fig.subplots_adjust(right=0.78)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)

def main() -> None:
    args = parse_args()
    frame = load_data(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    save_line_all(frame, args.output_dir / "mesh_throughput_line_all.png")
    save_line_non_bfs(frame, args.output_dir / "mesh_throughput_line_non_bfs.png")
    save_box_plot(frame, args.output_dir / "mesh_throughput_box.png")
    save_kde_plot(frame, args.output_dir / "mesh_throughput_kde.png")

    print("Generated plots in:", args.output_dir)


if __name__ == "__main__":
    main()
    
 