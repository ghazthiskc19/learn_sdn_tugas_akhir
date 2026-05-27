from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


TARGET_ALGORITHMS = ["astar", "dijkstra", "bellman-ford", "bfs"]
NON_BFS_ALGORITHMS = ["astar", "dijkstra", "bellman-ford"]
STYLE_MAP = {
	"astar": {"color": "#1f77b4", "linestyle": "-", "marker": "o", "label": "A*"},
	"dijkstra": {"color": "#ff7f0e", "linestyle": "--", "marker": "s", "label": "Dijkstra"},
	"bellman-ford": {
		"color": "#2ca02c",
		"linestyle": ":",
		"marker": "^",
		"label": "Bellman-Ford",
	},
	"bfs": {"color": "#d62728", "linestyle": "-.", "marker": "D", "label": "BFS"},
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate throughput visualizations from hierarchy_throughput.csv"
	)
	parser.add_argument(
		"--input",
		type=Path,
		default=Path(__file__).parent / "data" / "hierarchy_throughput.csv",
		help="Path to hierarchy throughput CSV.",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=Path(__file__).parent / "hierarchy",
		help="Directory to write generated plot images.",
	)
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


def algorithm_label(frame: pd.DataFrame, algorithm: str) -> str:
	style_label = STYLE_MAP[algorithm]["label"]
	algorithm_rows = frame[frame["algorithm"] == algorithm]
	if algorithm_rows.empty:
		return style_label
	hop_count = int(algorithm_rows["hop_count"].iloc[0])
	return f"{style_label} ({hop_count} hops)"


def style_axes(ax: plt.Axes) -> None:
	ax.grid(True, which="major", axis="both", linestyle="--", linewidth=0.7, alpha=0.3)
	ax.set_axisbelow(True)
	ax.set_xlabel("Second", fontsize=11)
	ax.set_ylabel("Throughput (Mbps)", fontsize=11)


def save_line_all(frame: pd.DataFrame, output_path: Path) -> None:
	fig, ax = plt.subplots(figsize=(12.5, 6.4))
	for algorithm in TARGET_ALGORITHMS:
		algo_frame = frame[frame["algorithm"] == algorithm]
		if algo_frame.empty:
			continue
		style = STYLE_MAP[algorithm]
		sns.lineplot(
			data=algo_frame,
			x="second",
			y="throughput_mbps",
			label=algorithm_label(frame, algorithm),
			color=style["color"],
			linestyle=style["linestyle"],
			marker=style["marker"],
			linewidth=2.1,
			markersize=4.2,
			ax=ax,
		)

	ax.set_title("Throughput Over Time - All Algorithms", fontsize=14, fontweight="bold")
	style_axes(ax)
	ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True, title="Algorithm")
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
		sns.lineplot(
			data=algo_frame,
			x="second",
			y="throughput_mbps",
			label=algorithm_label(frame, algorithm),
			color=style["color"],
			linestyle=style["linestyle"],
			marker=style["marker"],
			linewidth=2.2,
			markersize=4.5,
			ax=ax,
		)

	ax.set_title("Throughput Over Time - A*, Dijkstra, Bellman-Ford", fontsize=14, fontweight="bold")
	style_axes(ax)
	ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True, title="Algorithm")
	fig.tight_layout()
	fig.subplots_adjust(right=0.78)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_box_plot(frame: pd.DataFrame, output_path: Path) -> None:
	fig, ax = plt.subplots(figsize=(11.5, 6.2))

	order = [alg for alg in TARGET_ALGORITHMS if not frame.loc[frame["algorithm"] == alg].empty]
	plot_frame = frame.copy()
	plot_frame["algorithm_label"] = plot_frame["algorithm"].map(
		lambda a: algorithm_label(frame, a) if a in STYLE_MAP else a
	)
	label_order = [algorithm_label(frame, alg) for alg in order]
	palette = {algorithm_label(frame, alg): STYLE_MAP[alg]["color"] for alg in order}

	sns.boxplot(
		data=plot_frame,
		x="algorithm_label",
		y="throughput_mbps",
		order=label_order,
		palette=palette,
		ax=ax,
		showmeans=True,
		medianprops={"color": "#111111", "linewidth": 1.8},
		meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "#111111"},
	)

	ax.set_title("Throughput Distribution - Box Plot", fontsize=14, fontweight="bold")
	ax.set_ylabel("Throughput (Mbps)", fontsize=11)
	ax.grid(True, axis="y", linestyle="--", linewidth=0.7, alpha=0.3)
	ax.set_axisbelow(True)
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
			label=algorithm_label(frame, algorithm),
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

	line_all_path = args.output_dir / "hierarchy_visualize_throughput_line_all_1.png"
	line_no_bfs_path = args.output_dir / "hierarchy_visualize_throughput_line_no_bfs_1.png"
	box_path = args.output_dir / "hierarchy_visualize_throughput_box_1.png"
	kde_path = args.output_dir / "hierarchy_visualize_throughput_kde_1.png"

	save_line_all(frame, line_all_path)
	save_line_non_bfs(frame, line_no_bfs_path)
	save_box_plot(frame, box_path)
	save_kde_plot(frame, kde_path)

	print("Generated:")
	print(line_all_path)
	print(line_no_bfs_path)
	print(box_path)
	print(kde_path)


if __name__ == "__main__":
	main()