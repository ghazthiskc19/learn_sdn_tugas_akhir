#!/usr/bin/env python3
"""Compare results across multiple topologies."""

import argparse
import json
import os
from collections import defaultdict

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def load_results_from_dir(results_dir):
    """Load all results.json files from a directory and its subdirs."""
    all_results = {}
    for root, dirs, files in os.walk(results_dir):
        if 'results.json' in files:
            topology_name = os.path.basename(root)
            with open(os.path.join(root, 'results.json'), 'r') as f:
                all_results[topology_name] = json.load(f)
    return all_results


def aggregate_by_metric(results_dict):
    """Aggregate results by metric for each topology."""
    agg = {}
    for topology, results in results_dict.items():
        metrics = defaultdict(list)
        for r in results:
            metric_type = r.get('type')
            if metric_type:
                value = r.get('value')
                if value is not None and isinstance(value, (int, float)):
                    metrics[metric_type].append(value)
        agg[topology] = metrics
    return agg


def print_comparison_table(aggregated):
    """Print side-by-side comparison table."""
    if not aggregated:
        print("No data to compare")
        return
    
    # Collect all metric types
    all_metrics = set()
    for metrics in aggregated.values():
        all_metrics.update(metrics.keys())
    all_metrics = sorted(all_metrics)
    
    topologies = sorted(aggregated.keys())
    
    print("\n" + "="*80)
    print("TOPOLOGY COMPARISON".center(80))
    print("="*80)
    
    for metric in all_metrics:
        print(f"\n{metric}:")
        print(f"  {'Topology':<20} {'Count':<8} {'Mean':<12} {'Min':<12} {'Max':<12}")
        print(f"  {'-'*70}")
        
        for topo in topologies:
            values = aggregated[topo].get(metric, [])
            if values:
                count = len(values)
                mean = sum(values) / count
                min_val = min(values)
                max_val = max(values)
                print(f"  {topo:<20} {count:<8} {mean:<12.2f} {min_val:<12.2f} {max_val:<12.2f}")


def plot_metric_comparison(aggregated, metric_type, output_dir):
    """Plot a single metric across all topologies (box plot)."""
    if not MATPLOTLIB_AVAILABLE:
        return
    
    topologies = sorted(aggregated.keys())
    data = []
    labels = []
    
    for topo in topologies:
        values = aggregated[topo].get(metric_type, [])
        if values:
            data.append(values)
            labels.append(topo)
    
    if not data:
        return
    
    plt.figure(figsize=(10, 6))
    bp = plt.boxplot(data, labels=labels, patch_artist=True)
    
    # Color boxes
    colors = ['lightblue', 'lightgreen', 'lightcoral', 'lightyellow']
    for patch, color in zip(bp['boxes'], colors[:len(bp['boxes'])]):
        patch.set_facecolor(color)
    
    plt.ylabel(metric_type.replace('_', ' ').title())
    plt.xlabel('Topology')
    plt.title(f'{metric_type.replace("_", " ").title()} Comparison Across Topologies')
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    
    plot_path = os.path.join(output_dir, f'compare_{metric_type}.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    print(f"Plot saved: {plot_path}")


def plot_all_metrics_comparison(aggregated, output_dir):
    """Generate comparison plots for all metrics."""
    if not MATPLOTLIB_AVAILABLE:
        print("Matplotlib not available; skipping plots")
        return
    
    # Collect all metric types
    all_metrics = set()
    for metrics in aggregated.values():
        all_metrics.update(metrics.keys())
    
    for metric in sorted(all_metrics):
        plot_metric_comparison(aggregated, metric, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Compare experiment results across topologies")
    parser.add_argument('results_dir', help='Parent directory containing topology subdirs with results.json')
    parser.add_argument('--output-dir', default='comparison', help='Output directory for comparison plots')
    parser.add_argument('--table', action='store_true', help='Print comparison table')
    parser.add_argument('--plots', action='store_true', help='Generate comparison plots')
    parser.add_argument('--radar', action='store_true', help='Generate radar chart')
    parser.add_argument('--all', action='store_true', help='Generate all outputs (default)')
    
    args = parser.parse_args()
    
    # default to all if nothing specified
    if not (args.table or args.plots or args.radar):
        args.all = True
    
    results_dir = args.results_dir
    if not os.path.isdir(results_dir):
        print(f"Error: {results_dir} not found")
        return
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Loading results from {results_dir}...")
    all_results = load_results_from_dir(results_dir)
    
    if not all_results:
        print("No results.json files found in subdirectories")
        return
    
    print(f"Loaded {len(all_results)} topologies: {list(all_results.keys())}")
    
    aggregated = aggregate_by_metric(all_results)
    
    if args.all or args.table:
        print_comparison_table(aggregated)
    
    if args.all or args.plots:
        plot_all_metrics_comparison(aggregated, args.output_dir)
    
    print(f"\nComparison outputs saved to {args.output_dir}/")


if __name__ == '__main__':
    main()
