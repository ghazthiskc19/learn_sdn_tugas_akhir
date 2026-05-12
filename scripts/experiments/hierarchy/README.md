# Hierarchy Experiments

All scripts in this folder are standalone hierarchy topology experiments.

## Files
- `experiment_convergence_route.py`
- `experiment_latency_e2e.py`
- `experiment_throughput.py`
- `experiment_hop_count.py`

## Topology
These scripts are intended for `topology-hierarchy.py` only.

## Usage
Run them directly from this folder, for example:

```bash
python3 scripts/experiments/hierarchy/experiment_throughput.py
```

Each script can be run on its own and uses the shared hierarchy topology code from the same folder when available.