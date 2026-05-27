"""Helpers for loading link metrics from JSON files."""

import json


def load_link_metrics(path, metric_field, default_value=1):
    """Load undirected link metrics from a JSON file.

    Expected format:
        {"links": {"dpid1:dpid2": {"bandwidth_mbps": 100, "delay_ms": 2}}}
    """
    try:
        with open(path) as handle:
            data = json.load(handle)
        raw_links = data.get("links", {})
        metrics = {}
        for key, value in raw_links.items():
            left, right = (int(x) for x in key.split(":"))
            metric_value = value.get(metric_field, default_value)
            metrics[(left, right)] = metric_value
        return metrics
    except (FileNotFoundError, json.JSONDecodeError, ValueError, AttributeError):
        return {}


def build_directed_metric_dict(adjacency, undirected_metrics, default_value=1):
    """Expand undirected metrics to directed edge weights for adjacency graphs."""
    metrics = {}
    for src in adjacency:
        for dst, _ in adjacency[src]:
            key = (min(src, dst), max(src, dst))
            metric_value = undirected_metrics.get(key, default_value)
            metrics[(src, dst)] = metric_value
            metrics[(dst, src)] = metric_value
    return metrics


def bandwidth_to_costs(directed_metrics, ref_bandwidth=1000.0, min_bandwidth=1e-3, max_cost=1e9):
    """Convert directed bandwidth metrics (Mbps) to additive costs.

    Cost formula: cost = ref_bandwidth / bandwidth_mbps

    Guards:
    - Treat non-positive or missing bandwidths as very small bandwidth (min_bandwidth)
      to avoid division-by-zero and produce a large cost.
    - Clamp extremely large costs to max_cost.

    Args:
        directed_metrics: dict {(u, v): bandwidth_mbps}
        ref_bandwidth: reference bandwidth in Mbps (float)
        min_bandwidth: minimum treated bandwidth to avoid division by zero
        max_cost: upper clamp for cost values

    Returns:
        dict {(u, v): cost}
    """
    costs = {}
    for edge, bw in directed_metrics.items():
        try:
            bw_val = float(bw)
        except (TypeError, ValueError):
            bw_val = 0.0

        if bw_val <= 0.0:
            bw_val = min_bandwidth

        cost = float(ref_bandwidth) / bw_val
        if cost > max_cost:
            cost = max_cost
        costs[edge] = cost

    return costs