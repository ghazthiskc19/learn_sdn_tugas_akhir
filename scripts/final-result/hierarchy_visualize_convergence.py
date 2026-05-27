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
	"astar": "#1f77b4",
	"dijkstra": "#ff7f0e",
	"bellman-ford": "#2ca02c",
	"bfs": "#d62728",
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Generate separate convergence panels from hierarchy_convergence_end.csv"
	)
	parser.add_argument(
		"--input",
		type=Path,
		default=Path(__file__).parent / "data" / "hierarchy_convergence_end.csv",
		help="Path to hierarchy convergence CSV.",
	)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=Path(__file__).parent / "hierarchy",
		help="Directory to write generated plots.",
	)
	return parser.parse_args()


def load_data(csv_path: Path) -> pd.DataFrame:
	frame = pd.read_csv(csv_path)
	expected = {
		"scenario_type",
		"algorithm",
		"convergence_ms",
		"computation_time_us",
		"hop_count",
		"path",
		"nodes_visited",
		"queue_pops",
		"heap_pops",
		"relaxations",
	}
	missing = expected.difference(frame.columns)
	if missing:
		raise ValueError(f"Missing expected columns: {', '.join(sorted(missing))}")

	frame = frame.copy()
	frame["scenario_type"] = frame["scenario_type"].astype(str).str.strip().str.lower()
	frame["algorithm"] = frame["algorithm"].astype(str).str.strip().str.lower()
	for column in [
		"convergence_ms",
		"computation_time_us",
		"hop_count",
		"nodes_visited",
		"queue_pops",
		"heap_pops",
		"relaxations",
	]:
		frame[column] = pd.to_numeric(frame[column], errors="coerce")
	frame["path"] = frame["path"].astype(str).str.strip()
	return frame


def scenario_frame(frame: pd.DataFrame, scenario_type: str) -> pd.DataFrame:
	filtered = frame[(frame["scenario_type"] == scenario_type) & (frame["algorithm"].isin(TARGET_ALGORITHMS))].copy()
	filtered = filtered.dropna(subset=["algorithm"])
	return filtered.sort_values(["algorithm", "convergence_ms", "computation_time_us", "hop_count"])


def base_bar_style(ax: plt.Axes) -> None:
	ax.grid(True, axis="y", linestyle="--", linewidth=0.7, alpha=0.3)
	ax.set_axisbelow(True)


def bar_labels(ax: plt.Axes, bars) -> None:
	for bar in bars:
		height = bar.get_height()
		if pd.isna(height):
			continue
		ax.annotate(
			f"{height:,.1f}",
			xy=(bar.get_x() + bar.get_width() / 2, height),
			xytext=(0, 4),
			textcoords="offset points",
			ha="center",
			va="bottom",
			fontsize=9,
			fontweight="bold",
		)


def save_convergence_ms_plot(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_a")
	data = data.dropna(subset=["convergence_ms"])
	if data.empty:
		raise ValueError("No scenario_a convergence_ms data found.")

	fig, ax = plt.subplots(figsize=(9.6, 5.6))
	algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	values = [float(data.loc[data["algorithm"] == algo, "convergence_ms"].iloc[0]) for algo in algorithms]
	colors = [STYLE_MAP[algo] for algo in algorithms]
	bars = ax.bar([DISPLAY_NAME[a] for a in algorithms], values, color=colors, edgecolor="#1f1f1f", width=0.62)
	bar_labels(ax, bars)
	ax.set_title("Scenario A - Convergence Time (ms)", fontsize=14, fontweight="bold")
	ax.set_ylabel("convergence_ms", fontsize=11)
	base_bar_style(ax)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_computation_time_plot(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["computation_time_us"])
	if data.empty:
		raise ValueError("No scenario_b computation_time_us data found.")

	fig, ax = plt.subplots(figsize=(9.6, 5.6))
	algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	values = [float(data.loc[data["algorithm"] == algo, "computation_time_us"].iloc[0]) for algo in algorithms]
	colors = [STYLE_MAP[algo] for algo in algorithms]
	bars = ax.bar([DISPLAY_NAME[a] for a in algorithms], values, color=colors, edgecolor="#1f1f1f", width=0.62)
	bar_labels(ax, bars)
	ax.set_title("Scenario B - Computation Time (us)", fontsize=14, fontweight="bold")
	ax.set_ylabel("computation_time_us", fontsize=11)
	base_bar_style(ax)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_nodes_visited_plot(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["nodes_visited"])
	if data.empty:
		raise ValueError("No scenario_b nodes_visited data found.")

	fig, ax = plt.subplots(figsize=(9.6, 5.6))
	algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	values = [float(data.loc[data["algorithm"] == algo, "nodes_visited"].iloc[0]) for algo in algorithms]
	colors = [STYLE_MAP[algo] for algo in algorithms]
	bars = ax.bar([DISPLAY_NAME[a] for a in algorithms], values, color=colors, edgecolor="#1f1f1f", width=0.62)
	bar_labels(ax, bars)
	ax.set_title("Scenario B - Nodes Visited", fontsize=14, fontweight="bold")
	ax.set_ylabel("nodes_visited", fontsize=11)
	base_bar_style(ax)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_hop_count_plot(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["hop_count"])
	if data.empty:
		raise ValueError("No scenario_b hop_count data found.")

	fig, ax = plt.subplots(figsize=(9.6, 5.6))
	algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	values = [float(data.loc[data["algorithm"] == algo, "hop_count"].iloc[0]) for algo in algorithms]
	colors = [STYLE_MAP[algo] for algo in algorithms]
	bars = ax.bar([DISPLAY_NAME[a] for a in algorithms], values, color=colors, edgecolor="#1f1f1f", width=0.62)
	bar_labels(ax, bars)
	ax.set_title("Scenario B - Hop Count", fontsize=14, fontweight="bold")
	ax.set_ylabel("hop_count", fontsize=11)
	base_bar_style(ax)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_operation_stacked_bar(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["queue_pops", "heap_pops", "relaxations"])
	if data.empty:
		raise ValueError("No scenario_b operation metric data found.")

	fig, ax = plt.subplots(figsize=(10.2, 5.8))
	algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	x_positions = list(range(len(algorithms)))
	queue = [float(data.loc[data["algorithm"] == algo, "queue_pops"].iloc[0]) for algo in algorithms]
	heap = [float(data.loc[data["algorithm"] == algo, "heap_pops"].iloc[0]) for algo in algorithms]
	relax = [float(data.loc[data["algorithm"] == algo, "relaxations"].iloc[0]) for algo in algorithms]
	max_stack = max((q + h + r for q, h, r in zip(queue, heap, relax)), default=1.0)
	zero_height = max(0.15, max_stack * 0.001)

	def draw_segment(x_pos: float, bottom: float, value: float, color: str, label: str, zero_hatch: str | None = None):
		visible_value = value if value > 0 else zero_height
		bar = ax.bar(
			x_pos,
			visible_value,
			bottom=bottom,
			color=color if value > 0 else "white",
			edgecolor="#1f1f1f",
			width=0.62,
			label=label,
			hatch=zero_hatch if value <= 0 and zero_hatch else None,
			linewidth=1.0,
			alpha=1.0 if value > 0 else 0.9,
		)
		segment = bar[0]
		if value <= 0:
			segment.set_facecolor("white")
			segment.set_edgecolor(color)
			segment.set_linewidth(1.4)
			segment.set_hatch(zero_hatch or "///")
			label_y = bottom + visible_value + max_stack * 0.006
			ax.annotate(
				"0",
				xy=(x_pos, label_y),
				xytext=(0, 0),
				textcoords="offset points",
				ha="center",
				va="bottom",
				fontsize=8,
				fontweight="bold",
				color=color,
			)
		else:
			ax.annotate(
				f"{value:,.0f}",
				xy=(x_pos, bottom + visible_value / 2),
				xytext=(0, 0),
				textcoords="offset points",
				ha="center",
				va="center",
				fontsize=8,
				fontweight="bold",
				color="white" if visible_value > max_stack * 0.08 else "black",
			)
		return segment

	queue_bars = []
	heap_bars = []
	relax_bars = []
	for x_pos, q_val, h_val, r_val in zip(x_positions, queue, heap, relax):
		queue_bars.append(draw_segment(x_pos, 0, q_val, "#4c78a8", "queue_pops", zero_hatch="..."))
		heap_bars.append(draw_segment(x_pos, q_val, h_val, "#f58518", "heap_pops", zero_hatch="///"))
		relax_bars.append(draw_segment(x_pos, q_val + h_val, r_val, "#54a24b", "relaxations", zero_hatch="xxx"))

	ax.set_xticks(x_positions)
	ax.set_xticklabels([DISPLAY_NAME[a] for a in algorithms], fontsize=11)
	ax.set_ylabel("Operation count", fontsize=11)
	ax.set_title("Scenario B - Search Effort Breakdown", fontsize=14, fontweight="bold")
	ax.set_ylim(0, max_stack * 1.12)
	base_bar_style(ax)
	ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=True, title="Metric")
	fig.tight_layout()
	fig.subplots_adjust(right=0.8)
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_operation_table(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["queue_pops", "heap_pops", "relaxations"])
	if data.empty:
		raise ValueError("No scenario_b table data found.")

	table_data = []
	for algorithm in TARGET_ALGORITHMS:
		row = data[data["algorithm"] == algorithm]
		if row.empty:
			continue
		row = row.iloc[0]
		table_data.append(
			[
				DISPLAY_NAME[algorithm],
				int(row["queue_pops"]),
				int(row["heap_pops"]),
				int(row["relaxations"]),
				int(row["nodes_visited"]),
			]
		)

	fig, ax = plt.subplots(figsize=(9.5, 2.8))
	ax.axis("off")
	table = ax.table(
		cellText=table_data,
		colLabels=["Algorithm", "queue_pops", "heap_pops", "relaxations", "nodes_visited"],
		cellLoc="center",
		loc="center",
	)
	table.auto_set_font_size(False)
	table.set_fontsize(10)
	table.scale(1, 1.6)
	for (row_idx, col_idx), cell in table.get_celld().items():
		cell.set_edgecolor("#444444")
		if row_idx == 0:
			cell.set_facecolor("#e9eef5")
			cell.set_text_props(weight="bold")
		elif row_idx % 2 == 1:
			cell.set_facecolor("#f8f9fb")
		else:
			cell.set_facecolor("#ffffff")

	ax.set_title("Scenario B - Operation Metrics Table", fontsize=13, fontweight="bold", pad=12)
	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def save_path_panel(frame: pd.DataFrame, output_path: Path) -> None:
	data = scenario_frame(frame, "scenario_b")
	data = data.dropna(subset=["path"])
	if data.empty:
		raise ValueError("No scenario_b path data found.")

	fig, ax = plt.subplots(figsize=(12.8, 6.8))
	ax.set_title("Scenario B - Route Paths by Algorithm", fontsize=14, fontweight="bold", pad=14)
	ax.set_xlim(0, 1)
	ax.set_ylim(0, len([algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]) + 1)
	ax.axis("off")

	def draw_path_box(x: float, y: float, width: float, text: str) -> None:
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

	ordered_algorithms = [algo for algo in TARGET_ALGORITHMS if algo in data["algorithm"].values]
	for row_index, algorithm in enumerate(ordered_algorithms, start=1):
		row = data[data["algorithm"] == algorithm].iloc[0]
		path_nodes = [node.strip() for node in str(row["path"]).split("->") if node.strip()]
		y = len(ordered_algorithms) - row_index + 1
		color = STYLE_MAP[algorithm]

		ax.text(
			0.03,
			y,
			f"{DISPLAY_NAME[algorithm]} ({int(row['hop_count'])} hops)",
			fontsize=11,
			fontweight="bold",
			color=color,
			va="center",
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
			draw_path_box(x, y, box_width, node_name)

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

	fig.tight_layout()
	fig.savefig(output_path, dpi=200, bbox_inches="tight")
	plt.close(fig)


def main() -> None:
	args = parse_args()
	frame = load_data(args.input)
	args.output_dir.mkdir(parents=True, exist_ok=True)

	outputs = {
		"scenario_a_convergence_ms": args.output_dir / "hierarchy_visualize_convergence_scenario_a_convergence_ms_1.png",
		"scenario_b_computation_time": args.output_dir / "hierarchy_visualize_convergence_scenario_b_computation_time_us_1.png",
		"scenario_b_nodes_visited": args.output_dir / "hierarchy_visualize_convergence_scenario_b_nodes_visited_1.png",
		"scenario_b_operation_stacked": args.output_dir / "hierarchy_visualize_convergence_scenario_b_ops_stacked_bar_1.png",
		"scenario_b_operation_table": args.output_dir / "hierarchy_visualize_convergence_scenario_b_ops_table_1.png",
		"scenario_b_hop_count": args.output_dir / "hierarchy_visualize_convergence_scenario_b_hop_count_1.png",
		"scenario_b_path": args.output_dir / "hierarchy_visualize_convergence_scenario_b_path_1.png",
	}

	save_convergence_ms_plot(frame, outputs["scenario_a_convergence_ms"])
	save_computation_time_plot(frame, outputs["scenario_b_computation_time"])
	save_nodes_visited_plot(frame, outputs["scenario_b_nodes_visited"])
	save_operation_stacked_bar(frame, outputs["scenario_b_operation_stacked"])
	save_operation_table(frame, outputs["scenario_b_operation_table"])
	save_hop_count_plot(frame, outputs["scenario_b_hop_count"])
	save_path_panel(frame, outputs["scenario_b_path"])

	print("Generated:")
	for path in outputs.values():
		print(path)


if __name__ == "__main__":
	main()