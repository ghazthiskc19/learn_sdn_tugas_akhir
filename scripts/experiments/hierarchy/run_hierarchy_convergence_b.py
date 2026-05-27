#!/usr/bin/env python3
"""Hierarchy convergence benchmark for scenario B only.

Scenario B runs the phantom graph injection benchmark in-memory.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

from mininet.log import setLogLevel

from run_hierarchy_convergence import (
    DEFAULT_ALGORITHMS,
    RESULTS_DIR,
    run_phantom_algorithm,
    write_csv,
)


def run_scenario_b_only(algorithm: str) -> Dict[str, object]:
    result = run_phantom_algorithm(algorithm)
    return {**result.payload, "algorithm": result.algorithm, "controller": result.controller}


def resolve_algorithms(selected_algorithm: str) -> List[str]:
    if selected_algorithm == "all":
        return list(DEFAULT_ALGORITHMS)
    return [selected_algorithm]


def main() -> int:
    parser = argparse.ArgumentParser(description="Hierarchy convergence benchmark for scenario B")
    parser.add_argument("--output", default=str(RESULTS_DIR / "hierarchy_convergence_b.csv"), help="Path to CSV output")
    parser.add_argument("--algorithm", choices=["all", *DEFAULT_ALGORITHMS], default="all", help="Algorithm to run")
    parser.add_argument("--quiet", action="store_true", help="Reduce console output")
    args = parser.parse_args()

    verbose = not args.quiet
    setLogLevel("warning")
    output_path = Path(args.output)

    if verbose:
        print("[BOOT] hierarchy convergence scenario B starting")

    rows: List[Dict[str, object]] = []
    for algorithm in resolve_algorithms(args.algorithm):
        if verbose:
            print(f"[RUN] algorithm={algorithm} scenario_b")
        rows.append(run_scenario_b_only(algorithm))

    write_csv(rows, output_path)

    if verbose:
        print(f"[DONE] wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())