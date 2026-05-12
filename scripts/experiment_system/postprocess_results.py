#!/usr/bin/env python3
"""Post-process experiment results: JSON -> CSV + plots."""

import argparse
import csv
import json
import os
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def load_results(json_path):
    """Load results.json file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def flatten_results(results):
    """Convert nested result objects to flat CSV rows."""
    rows = []
    for r in results:
        row = {}
        for key, val in r.items():
            if isinstance(val, (list, dict)):
                # Skip complex types for now
                continue
            row[key] = val
        if row:  # only add non-empty rows
            rows.append(row)
    return rows


def write_csv(rows, output_path):
    """Write flat results to CSV."""
    if not rows:
        print(f"No data to write to CSV")
        return
    
    fieldnames = list(rows[0].keys())
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV written to {output_path}")


def aggregate_by_metric(results):
    """Aggregate results by metric type (throughput, latency, convergence, etc.)."""
    metrics = defaultdict(list)
    for r in results:
        metric_type = r.get('type')
        if metric_type:
            value = r.get('value')
            if value is not None:
                metrics[metric_type].append((r.get('trial', 0), value))
    return metrics


def plot_metrics(metrics, output_dir):
    """Generate plots for each metric type."""
    if not MATPLOTLIB_AVAILABLE:
        print("Matplotlib not available; skipping plots")
        return
    
    plots_created = []
    for metric_type, data in metrics.items():
        if not data:
            continue
        
        trials = [d[0] for d in data]
        values = [d[1] for d in data]
        
        # skip non-numeric values
        try:
            values = [float(v) if v is not None else 0 for v in values]
        except (ValueError, TypeError):
            continue
        
        plt.figure(figsize=(8, 5))
        plt.plot(trials, values, marker='o', linestyle='-', linewidth=2)
        plt.xlabel('Trial')
        plt.ylabel(metric_type)
        plt.title(f'{metric_type.replace("_", " ").title()} Over Trials')
        plt.grid(True, alpha=0.3)
        
        plot_path = os.path.join(output_dir, f'{metric_type}.png')
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        plots_created.append(plot_path)
        print(f"Plot saved: {plot_path}")
    
    return plots_created


def plot_throughput_comparison(results, output_dir):
    """Plot throughput by workload across trials."""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    workload_data = defaultdict(list)
    for r in results:
        if r.get('type') == 'throughput_mbps':
            wl = r.get('workload', 'unknown')
            val = r.get('value')
            trial = r.get('trial', 0)
            if val is not None:
                workload_data[wl].append((trial, float(val)))
    
    if not workload_data:
        return
    
    plt.figure(figsize=(10, 6))
    for wl, data in sorted(workload_data.items()):
        data_sorted = sorted(data, key=lambda x: x[0])
        trials = [d[0] for d in data_sorted]
        values = [d[1] for d in data_sorted]
        plt.plot(trials, values, marker='o', label=wl, linewidth=2)
    
    plt.xlabel('Trial')
    plt.ylabel('Throughput (Mbps)')
    plt.title('Throughput by Workload')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plot_path = os.path.join(output_dir, 'throughput_comparison.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"Comparison plot saved: {plot_path}")


def plot_latency_distribution(results, output_dir):
    """Plot latency distribution (box plot by trial)."""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    trial_latencies = defaultdict(list)
    for r in results:
        if r.get('type') == 'latency_ms':
            val = r.get('value')
            trial = r.get('trial', 0)
            if val is not None:
                try:
                    trial_latencies[trial].append(float(val))
                except (ValueError, TypeError):
                    pass
    
    if not trial_latencies:
        return
    
    trials = sorted(trial_latencies.keys())
    data_by_trial = [trial_latencies[t] for t in trials]
    
    plt.figure(figsize=(8, 5))
    plt.boxplot(data_by_trial, labels=[f'Trial {t}' for t in trials])
    plt.ylabel('Latency (ms)')
    plt.title('Latency Distribution Across Trials')
    plt.grid(True, alpha=0.3, axis='y')
    
    plot_path = os.path.join(output_dir, 'latency_distribution.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"Distribution plot saved: {plot_path}")


def plot_convergence_times(results, output_dir):
    """Plot route convergence times for events."""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    convergence_data = []
    for r in results:
        if r.get('event'):
            conv = r.get('convergence')
            if isinstance(conv, dict) and 'icmp_convergence_s' in conv:
                convergence_data.append((r.get('trial', 0), conv['icmp_convergence_s']))
    
    if not convergence_data:
        return
    
    trials = [d[0] for d in convergence_data]
    values = [d[1] for d in convergence_data]
    
    plt.figure(figsize=(8, 5))
    plt.bar(trials, values, color='steelblue', alpha=0.7)
    plt.xlabel('Trial')
    plt.ylabel('Convergence Time (s)')
    plt.title('Route Convergence Time After Link Failure')
    plt.grid(True, alpha=0.3, axis='y')
    
    plot_path = os.path.join(output_dir, 'convergence_times.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"Convergence plot saved: {plot_path}")


def generate_summary_stats(results, output_dir):
    """Generate summary statistics file."""
    metrics = aggregate_by_metric(results)
    
    summary = []
    summary.append("Experiment Results Summary\n" + "="*40)
    
    for metric_type, data in sorted(metrics.items()):
        if not data:
            continue
        values = [v for t, v in data if isinstance(v, (int, float))]
        if not values:
            continue
        
        summary.append(f"\n{metric_type}:")
        summary.append(f"  Count: {len(values)}")
        summary.append(f"  Mean: {sum(values) / len(values):.2f}")
        summary.append(f"  Min: {min(values):.2f}")
        summary.append(f"  Max: {max(values):.2f}")
    
    summary_text = "\n".join(summary)
    summary_path = os.path.join(output_dir, 'summary.txt')
    with open(summary_path, 'w') as f:
        f.write(summary_text)
    print(f"Summary written to {summary_path}")
    print(summary_text)


def main():
    parser = argparse.ArgumentParser(description="Post-process experiment results")
    parser.add_argument('results_json', help='Path to results.json')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: same as results.json)')
    parser.add_argument('--csv', action='store_true', help='Generate CSV output')
    parser.add_argument('--plots', action='store_true', help='Generate plots')
    parser.add_argument('--summary', action='store_true', help='Generate summary statistics')
    parser.add_argument('--all', action='store_true', help='Generate all outputs (default)')
    
    args = parser.parse_args()
    
    # default to all if nothing specified
    if not (args.csv or args.plots or args.summary):
        args.all = True
    
    results_json = args.results_json
    if not os.path.exists(results_json):
        print(f"Error: {results_json} not found")
        return
    
    results_dir = args.output_dir or os.path.dirname(results_json) or '.'
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"Loading {results_json}...")
    results = load_results(results_json)
    print(f"Loaded {len(results)} result entries")
    
    if args.all or args.csv:
        rows = flatten_results(results)
        csv_path = os.path.join(results_dir, 'results.csv')
        write_csv(rows, csv_path)
    
    if args.all or args.plots:
        metrics = aggregate_by_metric(results)
        plot_metrics(metrics, results_dir)
        plot_throughput_comparison(results, results_dir)
        plot_latency_distribution(results, results_dir)
        plot_convergence_times(results, results_dir)
    
    if args.all or args.summary:
        generate_summary_stats(results, results_dir)


if __name__ == '__main__':
    main()
