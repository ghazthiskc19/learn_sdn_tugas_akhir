from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import pandas as pd


TARGET_ALGORITHMS = ["astar", "dijkstra", "bellman-ford", "bfs"]
DISPLAY_NAME = {
	"astar": "A*",
	"dijkstra": "Dijkstra",
	"bellman-ford": "Bellman-Ford",
	"bfs": "BFS",
}
STYLE_MAP = {
	"astar": {"color": "#1f77b4"},
	"dijkstra": {"color": "#ff7f0e"},
	"bellman-ford": {"color": "#2ca02c"},
	"bfs": {"color": "#d62728"},
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Plot hop count and path structure for hierarchy latency results."
	)
	parser.add_argument(
		"--input",
		type=Path,
		default=Path(__file__).parent / "data" / "hierarchy_latency.csv",
		help="Path to the latency CSV file.",
	)
	parser.add_argument(
		"--output",
		type=Path,
		default=Path(__file__).parent / "hierarchy" / "hierarchy_hop_count.png",
		help="Output image path.",
	)
	parser.add_argument(
		"--show",
		action="store_true",
		help="Show the plot in a window after saving it.",
	)
	return parser.parse_args()


def load_summary(csv_path: Path) -> pd.DataFrame:
	frame = pd.read_csv(csv_path)

	expected_columns = {"algorithm", "hop_count", "path", "include_in_analysis"}
	missing_columns = expected_columns.difference(frame.columns)
	if missing_columns:
		missing_list = ", ".join(sorted(missing_columns))
		raise ValueError(f"Missing expected columns: {missing_list}")

	frame = frame.copy()
	frame["algorithm"] = frame["algorithm"].astype(str).str.strip().str.lower()
	frame["hop_count"] = pd.to_numeric(frame["hop_count"], errors="coerce")
	frame["include_in_analysis"] = pd.to_numeric(
		frame["include_in_analysis"], errors="coerce"
	).fillna(0)
	frame["path"] = frame["path"].astype(str).str.strip()

	frame = frame[frame["include_in_analysis"] == 1]
	frame = frame[frame["algorithm"].isin(TARGET_ALGORITHMS)]
	frame = frame.dropna(subset=["hop_count", "path"])

	summary = (
		frame.sort_values(["algorithm", "hop_count", "path"])
		.drop_duplicates(subset=["algorithm"], keep="first")
		.loc[:, ["algorithm", "hop_count", "path"]]
	)

	ordered_rows = []
	for algorithm in TARGET_ALGORITHMS:
		match = summary[summary["algorithm"] == algorithm]
		if not match.empty:
			ordered_rows.append(match.iloc[0])

	if not ordered_rows:
		raise ValueError("No analysis rows found for the target algorithms.")

	return pd.DataFrame(ordered_rows).reset_index(drop=True)


def draw_hop_count_panel(ax: plt.Axes, summary: pd.DataFrame) -> None:
	algorithms = summary["algorithm"].tolist()
	hop_counts = summary["hop_count"].tolist()
	colors = [STYLE_MAP[algorithm]["color"] for algorithm in algorithms]
	x_positions = list(range(len(algorithms)))

	bars = ax.bar(x_positions, hop_counts, color=colors, width=0.62, edgecolor="#1f1f1f")
	max_hop = max(hop_counts) if hop_counts else 0

	for bar, hop_count in zip(bars, hop_counts):
		ax.annotate(
			f"{int(hop_count)} hops",
			xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
			xytext=(0, 10),
			textcoords="offset points",
			ha="center",
			va="bottom",
			fontsize=10,
			fontweight="bold",
		)

	ax.set_xticks(x_positions)
	ax.set_xticklabels([DISPLAY_NAME[algorithm] for algorithm in algorithms], fontsize=11)
	ax.set_ylabel("Hop count", fontsize=12)
	ax.set_title("Hop Count by Algorithm", fontsize=15, fontweight="bold")
	ax.set_ylim(0, max_hop + 0.8)
	ax.grid(True, axis="y", linestyle="--", linewidth=0.7, alpha=0.3)
	ax.set_axisbelow(True)


def draw_path_box(ax: plt.Axes, x: float, y: float, text: str, width: float) -> None:
	box = FancyBboxPatch(
		(x, y - 0.22),
		width,
		0.44,
		boxstyle="round,pad=0.03,rounding_size=0.06",
		linewidth=1.0,
		edgecolor="#3a3a3a",
		facecolor="#f8f9fb",
	)
	ax.add_patch(box)
	ax.text(x + width / 2, y, text, ha="center", va="center", fontsize=10)


def draw_path_panel(ax: plt.Axes, summary: pd.DataFrame) -> None:
	ax.set_title("Path Structure and Hop Count Relationship", fontsize=15, fontweight="bold")
	ax.set_xlim(0, 1)
	ax.set_ylim(0, len(summary) + 1)
	ax.axis("off")

	for row_index, row in enumerate(summary.itertuples(index=False), start=1):
		algorithm = row.algorithm
		path_nodes = [node.strip() for node in str(row.path).split("->")]
		path_nodes = [node for node in path_nodes if node]
		if not path_nodes:
			continue

		y = len(summary) - row_index + 1
		color = STYLE_MAP[algorithm]["color"]

		ax.text(
			0.03,
			y,
			f"{DISPLAY_NAME[algorithm]}  ({int(row.hop_count)} hops)",
			va="center",
			ha="left",
			fontsize=11,
			fontweight="bold",
			color=color,
		)

		start_x = 0.31
		end_x = 0.97
		usable_width = end_x - start_x
		box_width = min(0.13, max(0.075, usable_width / max(len(path_nodes) * 1.45, 1)))
		gap = 0.03
		step = box_width + gap
		total_width = len(path_nodes) * box_width + (len(path_nodes) - 1) * gap
		if total_width > usable_width:
			gap = max(0.01, (usable_width - len(path_nodes) * box_width) / max(len(path_nodes) - 1, 1))
			step = box_width + gap

		left_edge = start_x
		if total_width < usable_width:
			left_edge = start_x + (usable_width - total_width) / 2

		for node_index, node_name in enumerate(path_nodes):
			x = left_edge + node_index * step
			draw_path_box(ax, x, y, node_name, box_width)

			if node_index < len(path_nodes) - 1:
				arrow = FancyArrowPatch(
					(x + box_width, y),
					(x + box_width + gap, y),
					arrowstyle="->",
					mutation_scale=12,
					linewidth=1.2,
					color=color,
				)
				ax.add_patch(arrow)

		# ax.text(
		# 	0.98,
		# 	y - 0.27,
		# 	" -> ".join(path_nodes),
		# 	ha="right",
		# 	va="center",
		# 	fontsize=8.5,
		# 	color="#555555",
		# )


def plot_hop_count(summary: pd.DataFrame, output_path: Path) -> None:
	fig, (ax_top, ax_bottom) = plt.subplots(
		2,
		1,
		figsize=(16, 10),
		gridspec_kw={"height_ratios": [1, 1.35]},
	)

	draw_hop_count_panel(ax_top, summary)
	draw_path_panel(ax_bottom, summary)

	fig.suptitle(
		"Hierarchy Hop Count and Route Path Overview",
		fontsize=17,
		fontweight="bold",
		y=0.98,
	)
	fig.tight_layout(rect=(0, 0, 1, 0.96))
	fig.savefig(output_path, dpi=200, bbox_inches="tight")


def main() -> None:
	args = parse_args()
	summary = load_summary(args.input)
	plot_hop_count(summary, args.output)

	if args.show:
		plt.show()


if __name__ == "__main__":
	main()