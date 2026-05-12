#!/usr/bin/env python3
"""Run experiments across multiple topologies and generate comparison plots."""

import argparse
import os
import subprocess
import sys
import time


def run_experiment(config_file, skip_plots=False):
    """Run a single experiment config."""
    print(f"\n{'='*60}")
    print(f"Running experiment: {config_file}")
    print('='*60)
    
    cmd = ['python3', 'scripts/experiment_system/experiment_runner.py', config_file]
    if skip_plots:
        cmd.append('--no-plots')
    
    result = subprocess.run(cmd, cwd='/workspaces/learn_sdn')
    return result.returncode == 0


def compare_results(results_parent_dir, output_dir='comparison'):
    """Generate comparison plots and tables."""
    print(f"\n{'='*60}")
    print("Generating comparison plots and statistics...")
    print('='*60)
    
    cmd = ['python3', 'scripts/experiment_system/compare_topologies.py', results_parent_dir, 
           '--output-dir', output_dir, '--all']
    
    result = subprocess.run(cmd, cwd='/workspaces/learn_sdn')
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Run experiments across multiple topologies")
    parser.add_argument('--topologies', nargs='+', default=['hierarchy', 'mesh'],
                       help='List of topologies to test (default: hierarchy and mesh)')
    parser.add_argument('--skip-plots', action='store_true', help='Skip individual topology plots')
    parser.add_argument('--no-compare', action='store_true', help='Skip comparison analysis')
    parser.add_argument('--results-dir', default='results', help='Parent results directory')
    parser.add_argument('--comparison-output', default='comparison', help='Comparison output directory')
    
    args = parser.parse_args()
    
    os.makedirs(args.results_dir, exist_ok=True)
    
    successful = []
    failed = []
    
    # Run experiments for each topology
    for topo in args.topologies:
        config_file = f'scripts/experiments/{topo}.yaml'
        if not os.path.exists(config_file):
            print(f"Warning: {config_file} not found, skipping {topo}")
            failed.append((topo, "config not found"))
            continue
        
        try:
            if run_experiment(config_file, args.skip_plots):
                successful.append(topo)
            else:
                failed.append((topo, "runner failed"))
        except Exception as e:
            print(f"Error running {topo}: {e}")
            failed.append((topo, str(e)))
        
        time.sleep(2)  # brief pause between experiments
    
    # Print summary
    print(f"\n{'='*60}")
    print("EXPERIMENT SUMMARY")
    print('='*60)
    print(f"Successful: {len(successful)}/{len(args.topologies)}")
    for topo in successful:
        print(f"  ✓ {topo}")
    
    if failed:
        print(f"\nFailed: {len(failed)}/{len(args.topologies)}")
        for topo, reason in failed:
            print(f"  ✗ {topo}: {reason}")
    
    # Generate comparison if requested
    if not args.no_compare and successful:
        print("\nGenerating comparison plots...")
        if compare_results(args.results_dir, args.comparison_output):
            print(f"Comparison plots saved to {args.comparison_output}/")
        else:
            print("Comparison generation failed")
    
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
