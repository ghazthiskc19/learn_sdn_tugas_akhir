# Experiment System

This folder contains the runnable Python tools for experiments.

## Files

- `experiment_runner.py`: builds a topology from config, runs workloads, and saves raw results.
- `run_experiment.py`: simple interactive launcher for hierarchy and mesh experiments.
- `run_all_experiments.py`: runs multiple topology configs and then compares them.
- `compare_topologies.py`: reads results from several topologies and prints/plots comparisons.
- `postprocess_results.py`: converts raw results into CSV, plots, and summary statistics.
- `metrics.py`: shared parsers and helpers used by the runners.

## Usage

From the repository root:

```bash
python3 scripts/experiment_system/run_experiment.py
python3 scripts/experiment_system/experiment_runner.py scripts/experiments/hierarchy.yaml
python3 scripts/experiment_system/run_all_experiments.py
```

The topology configs still live in `scripts/experiments/`.
