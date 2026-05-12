#!/usr/bin/env python3
"""
Simple experiment launcher for SDN experiments.

Usage examples:
    python3 scripts/experiment_system/run_experiment.py
    python3 scripts/experiment_system/run_experiment.py --topology hierarchy --metric throughput
    python3 scripts/experiment_system/run_experiment.py --topology mesh --metric convergence
"""

import argparse
import os
import subprocess
import sys


BASE_DIR = os.path.dirname(os.path.realpath(__file__))
SCRIPTS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))

EXPERIMENTS = {
    'hierarchy': {
        'convergence': os.path.join(SCRIPTS_DIR, 'experiments', 'hierarchy', 'experiment_convergence_route.py'),
        'latency': os.path.join(SCRIPTS_DIR, 'experiments', 'hierarchy', 'experiment_latency_e2e.py'),
        'throughput': os.path.join(SCRIPTS_DIR, 'experiments', 'hierarchy', 'experiment_throughput.py'),
        'hopcount': os.path.join(SCRIPTS_DIR, 'experiments', 'hierarchy', 'experiment_hop_count.py'),
    },
    'mesh': {
        'convergence': os.path.join(SCRIPTS_DIR, 'experiments', 'mesh', 'experiment_convergence_route.py'),
        'latency': os.path.join(SCRIPTS_DIR, 'experiments', 'mesh', 'experiment_latency_e2e.py'),
        'throughput': os.path.join(SCRIPTS_DIR, 'experiments', 'mesh', 'experiment_throughput.py'),
        'hopcount': os.path.join(SCRIPTS_DIR, 'experiments', 'mesh', 'experiment_hop_count.py'),
    },
}


def choose_from_menu() -> tuple[str, str]:
    print('\nAvailable experiments:')
    options = []
    index = 1
    for topology in ('hierarchy', 'mesh'):
        for metric in sorted(EXPERIMENTS[topology].keys()):
            options.append((topology, metric))
            print(f'  {index}. {topology} / {metric}')
            index += 1
    print('')

    while True:
        choice = input('Pilih nomor eksperimen: ').strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        print('Pilihan tidak valid. Coba lagi.')


def build_command(script_path: str, forward_args: list[str]) -> list[str]:
    if not os.path.exists(script_path):
        raise FileNotFoundError(f'Script not found: {script_path}')
    return [sys.executable, script_path, *forward_args]


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Simple launcher for hierarchy and mesh experiment scripts'
    )
    parser.add_argument(
        '--topology',
        choices=sorted(EXPERIMENTS.keys()),
        help='Topologi yang mau dijalankan (default: interactive menu)'
    )
    parser.add_argument(
        '--metric',
        choices=['convergence', 'latency', 'throughput', 'hopcount'],
        help='Metrik yang mau dijalankan (default: interactive menu)'
    )
    parser.add_argument('--controller-cmd', help='Forward to experiment script', default=None)
    parser.add_argument('--algo-name', help='Forward to experiment script', default=None)
    parser.add_argument('--output-dir', help='Forward to experiment script', default=None)
    parser.add_argument('--no-controller', help='Forward to experiment script', action='store_true')
    parser.add_argument('--verbose', help='Forward to experiment script', action='store_true')
    args = parser.parse_args(argv)

    if args.topology and args.metric:
        topology = args.topology
        metric = args.metric
    elif args.topology or args.metric:
        parser.error('Gunakan --topology dan --metric bersama, atau jalankan tanpa argumen untuk menu interaktif.')
    else:
        topology, metric = choose_from_menu()

    script_path = EXPERIMENTS.get(topology, {}).get(metric)
    if not script_path:
        raise SystemExit(f'Experiment not available: {topology}/{metric}')

    forward_args = []
    if args.controller_cmd:
        forward_args.extend(['--controller-cmd', args.controller_cmd])
    if args.algo_name:
        forward_args.extend(['--algo-name', args.algo_name])
    if args.output_dir:
        forward_args.extend(['--output-dir', args.output_dir])
    if args.no_controller:
        forward_args.append('--no-controller')
    if args.verbose:
        forward_args.append('--verbose')

    cmd = build_command(script_path, forward_args)
    print(f'\nMenjalankan: {topology} / {metric}')
    print('Command:', ' '.join(cmd))
    print('')
    completed = subprocess.run(cmd)
    raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
