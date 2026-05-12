# Experiment Layout

This folder separates experiments by topology so hierarchy-specific and mesh-specific runs do not mix.

## Hierarchy

Use `scripts/experiments/hierarchy/` for the four hierarchy-only experiments:
- route convergence time
- end-to-end latency
- throughput
- hop count

## Mesh

Use `scripts/experiments/mesh/` for mesh-specific experiments and future mesh criteria.

## Compatibility

The utility scripts that used to live in `scripts/` now live in `scripts/experiment_system/`. The topology-specific experiment entrypoints stay in this folder tree for clarity.