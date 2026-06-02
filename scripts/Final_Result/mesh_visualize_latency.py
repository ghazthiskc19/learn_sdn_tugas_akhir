from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


TARGET_ALGORITHMS = ["astar", "dijkstra", "bellman-ford", "bfs"]
STYLE_MAP = {
	"astar": {"color": "#1f77b4", "linestyle": "-", "marker": "o", "linewidth": 2.6},
	"dijkstra": {"color": "#ff7f0e", "linestyle": "--", "marker": "s", "linewidth": 2.4},
	"bellman-ford": {"color": "#2ca02c", "linestyle": ":", "marker": "^", "linewidth": 2.4},
	"bfs": {"color": "#d62728", "linestyle": "-.", "marker": "D", "linewidth": 2.4},
}
DISPLAY_NAME = {
	"astar": "A*",
	"dijkstra": "Dijkstra",
	"bellman-ford": "Bellman-Ford",
	"bfs": "BFS",
}
LABEL_OFFSETS = {
	"astar": (8, 0),
	"dijkstra": (8, 8),
	"bellman-ford": (8, -8),
	"bfs": (8, 14),
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Plot mesh latency as a single-panel line chart."
	)
	parser.add_argument(
		"--input",
		type=Path,
		default=Path(__file__).parent / "data" / "mesh_latency.csv",
		help="Path to the mesh latency CSV file.",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=Path(__file__).parent / "mesh_latency_lineplot.png",
		help="Output image path.",
	)
	parser.add_argument(
		"--show",
		action="store_true",
		help="Show the plot in a window after saving it.",
	)
	return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
	frame = pd.read_csv(csv_path)

	expected_columns = {"algorithm", "icmp_seq", "rtt_ms", "include_in_analysis"}
	missing_columns = expected_columns.difference(frame.columns)
	if missing_columns:
		missing_list = ", ".join(sorted(missing_columns))
		raise ValueError(f"Missing expected columns: {missing_list}")

	frame = frame.copy()
	frame["algorithm"] = frame["algorithm"].astype(str).str.strip().str.lower()
	frame["icmp_seq"] = pd.to_numeric(frame["icmp_seq"], errors="coerce")
	frame["rtt_ms"] = pd.to_numeric(frame["rtt_ms"], errors="coerce")
	frame["include_in_analysis"] = pd.to_numeric(
		frame["include_in_analysis"], errors="coerce"
	).fillna(0)

	frame = frame[frame["include_in_analysis"] == 1]
	frame = frame[frame["algorithm"].isin(TARGET_ALGORITHMS)]
	frame = frame.dropna(subset=["icmp_seq", "rtt_ms"])
	frame = frame.sort_values(["algorithm", "icmp_seq"])

	return frame


def plot_latency(frame: pd.DataFrame, output_path: Path) -> None:
	if frame.empty:
		raise ValueError("No analysis rows found for the target algorithms.")

	fig, ax = plt.subplots(figsize=(12.5, 6.8))

	for algorithm in TARGET_ALGORITHMS:
		algo_frame = frame[frame["algorithm"] == algorithm]
		if algo_frame.empty:
			continue

		style = STYLE_MAP[algorithm]
		ax.plot(
			algo_frame["icmp_seq"],
			algo_frame["rtt_ms"],
			label=DISPLAY_NAME[algorithm],
			color=style["color"],
			linestyle=style["linestyle"],
			marker=style["marker"],
			linewidth=style["linewidth"],
			markersize=5.5,
			markerfacecolor="white",
			markeredgewidth=1.2,
			alpha=0.98,
		)

		last_point = algo_frame.iloc[-1]
		offset_x, offset_y = LABEL_OFFSETS[algorithm]
		ax.annotate(
			DISPLAY_NAME[algorithm],
			xy=(last_point["icmp_seq"], last_point["rtt_ms"]),
			xytext=(offset_x, offset_y),
			textcoords="offset points",
			va="center",
			fontsize=10,
			color=style["color"],
			fontweight="bold",
		)

	ax.set_title("Mesh Latency vs ICMP Sequence", fontsize=15, fontweight="bold")
	ax.set_xlabel("icmp_seq", fontsize=12)
	ax.set_ylabel("rtt_ms", fontsize=12)

	ax.grid(True, which="major", axis="both", linestyle="--", linewidth=0.7, alpha=0.35)
	ax.set_axisbelow(True)

	handles, labels = ax.get_legend_handles_labels()
	ax.legend(
		handles,
		labels,
		loc="upper left",
		bbox_to_anchor=(1.02, 1.0),
		frameon=True,
		title="Algorithm",
	)

	fig.tight_layout()
	fig.subplots_adjust(right=0.8)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")


def main() -> None:
	args = parse_args()
	frame = load_data(args.input)
	plot_latency(frame, args.output)

	if args.show:
		plt.show()


if __name__ == "__main__":
	main()