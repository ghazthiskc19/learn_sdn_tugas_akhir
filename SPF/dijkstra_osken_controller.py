"""Dijkstra SPF OpenFlow controller.

Single-source shortest path forwarding using Dijkstra's algorithm.
Inherits all SDN infrastructure from SPFBaseController; adds only the
path-computation algorithm.

Complexity:   O((V+E) log V) per path query
Metric:       hop count (all edges weight 1)
Multipath:    no - single best path per (src, dst)
ECMP:         no

Run:
    python3 dijkstra_osken_controller.py
    python3 dijkstra_osken_controller.py --verbose

See Also:
    astar_osken_controller.py              - same metric, guided search
    dijkstra_multipath_osken_controller.py - adds ECMP over equal-cost paths
"""

import os
import sys

from base_controller import SPFBaseController
from algorithms.dijkstra import dijkstra
from algorithms.weight_utils import build_directed_metric_dict, load_link_metrics, bandwidth_to_costs

# Kept as module-level constants for backward compatibility:
# dijkstra_multipath_osken_controller.py imports these by name.
SPF_FLOW_COOKIE = 0x5346500000000001
SPF_FLOW_COOKIE_MASK = 0xFFFFFFFFFFFFFFFF
SPF_FLOW_PRIORITY = 100

WEIGHTS_FILE = os.environ.get(
    "SPF_WEIGHTS_FILE",
    os.path.join(os.path.dirname(__file__), "link_weights.json"),
)
WEIGHT_FIELD = os.environ.get("SPF_WEIGHT_FIELD", "bandwidth_mbps")
REF_BANDWIDTH = float(os.environ.get("SPF_REF_BANDWIDTH", "1000"))


def _load_weights(path):
    """Load link weights from JSON; return {} if file is absent or malformed."""
    return load_link_metrics(path, WEIGHT_FIELD)


class DijkstraSwitch(SPFBaseController):
    """Single shortest-path forwarding using Dijkstra's algorithm.

    Overrides compute_path() to call algorithms/dijkstra.py.
    All SDN infrastructure (topology, host learning, flows, flooding)
    is provided by SPFBaseController.
    """

    FLOW_COOKIE = SPF_FLOW_COOKIE

    def __init__(self, *args, **kwargs):
        super(DijkstraSwitch, self).__init__(*args, **kwargs)
        raw_weights = _load_weights(WEIGHTS_FILE)
        if raw_weights:
            self.logger.info("[DJ-WEIGHTS] loaded %d link weights from %s",
                             len(raw_weights), WEIGHTS_FILE)
        else:
            self.logger.info("[DJ-WEIGHTS] no weight file; using hop-count metric")

    def _build_weight_dict(self):
        """Build weights dict keyed by (u, v) from the current adjacency.

        We reload the JSON each time so weighted runs can pick up runtime
        changes without relying on process restart ordering.
        """
        link_weights = _load_weights(WEIGHTS_FILE)
        if not link_weights:
            return None
        directed = build_directed_metric_dict(self.adjacency, link_weights)
        # If weights represent bandwidth, convert to additive cost
        if WEIGHT_FIELD == "bandwidth_mbps":
            return bandwidth_to_costs(directed, ref_bandwidth=REF_BANDWIDTH)
        return directed

    def compute_path(self, src, dst, first_port, final_port):
        """Compute shortest path using Dijkstra's algorithm.

        Algorithm steps:
            1. Run Dijkstra from src - O((V+E) log V)
            2. Reconstruct path by following predecessor pointers
        """
        self.logger.debug("[PATH-QUERY] Dijkstra: s%d -> s%d", src, dst)

        weights = self._build_weight_dict()

        # --- Phase 1: Run Dijkstra from source switch ---
        # Returns distance[v] = min hop count from src to v
        #         previous[v] = predecessor of v on the shortest path
        distance, previous = dijkstra(self.adjacency, src, weights=weights)

        reachable = sum(1 for d in distance.values() if d != float("inf"))
        self.logger.info("[SPF-DONE] s%d->s%d reachable=%d/%d",
                         src, dst, reachable, len(distance))

        # --- Phase 2: Reconstruct path from predecessor pointers ---
        return self._reconstruct_path(src, dst, first_port, final_port, distance, previous)


if __name__ == '__main__':
    current_file = os.path.abspath(__file__)
    passthrough_args = sys.argv[1:]
    if '--observe-links' not in passthrough_args:
        passthrough_args = ['--observe-links'] + passthrough_args
    sys.argv = ['dijkstra_osken_controller', *passthrough_args, current_file]
    from os_ken.cmd.manager import main
    import sys as _sys
    _sys.exit(main())
