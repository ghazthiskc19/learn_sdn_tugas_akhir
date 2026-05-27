#!/usr/bin/env python3
"""Hierarchy convergence benchmark for scenario A only.

Scenario A measures controller convergence on the real Hierarchy topology
when the Core1-Core3 link is flapped.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Dict, List

from mininet.log import setLogLevel

from run_hierarchy_convergence import (
    DEFAULT_ALGORITHMS,
    OF_PORT,
    RESULTS_DIR,
    mininet_cleanup,
    run_scenario_a,
    write_csv,
    write_delay_weights,
)


def run_scenario_a_only(algorithm: str, weights_file: Path, ofp_port: int, verbose: bool) -> Dict[str, object]:
    result = run_scenario_a(algorithm, weights_file, ofp_port, verbose)
    return {**result.payload, "algorithm": result.algorithm, "controller": result.controller}


def resolve_algorithms(selected_algorithm: str) -> List[str]:
    if selected_algorithm == "all":
        return list(DEFAULT_ALGORITHMS)
    return [selected_algorithm]


def main() -> int:
    parser = argparse.ArgumentParser(description="Hierarchy convergence benchmark for scenario A")
    parser.add_argument("--output", default=str(RESULTS_DIR / "hierarchy_convergence_a.csv"), help="Path to CSV output")
    parser.add_argument("--algorithm", choices=["all", *DEFAULT_ALGORITHMS], default="all", help="Algorithm to run")
    parser.add_argument("--quiet", action="store_true", help="Reduce console output")
    args = parser.parse_args()

    verbose = not args.quiet
    setLogLevel("warning")
    output_path = Path(args.output)

    if verbose:
        print("[BOOT] hierarchy convergence scenario A starting")

    with tempfile.TemporaryDirectory(prefix="hierarchy_conv_a_weights_") as temp_dir:
        weights_file = Path(temp_dir) / "hierarchy_delay_weights.json"
        write_delay_weights(weights_file)
        rows: List[Dict[str, object]] = []

        for algorithm in resolve_algorithms(args.algorithm):
            if verbose:
                print(f"[RUN] algorithm={algorithm} scenario_a")
            mininet_cleanup()
            rows.append(run_scenario_a_only(algorithm, weights_file, OF_PORT, verbose))

        write_csv(rows, output_path)

    if verbose:
        print(f"[DONE] wrote {len(rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())