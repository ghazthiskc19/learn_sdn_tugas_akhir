"""A* SPF OpenFlow controller.

Single-pair shortest path forwarding using A* search with a reverse-BFS
hop-count heuristic. On networks where the metric is hop count, A* visits
fewer nodes than Dijkstra by using the heuristic to prune the search.

Complexity:   O((V+E) log V) worst-case; typically O(E) with a good heuristic
Metric:       hop count (all edges weight 1)
Heuristic:    reverse-BFS hop distance from destination
Multipath:    no - single best path per (src, dst)
ECMP:         no

Run:
    python3 astar_osken_controller.py
    python3 astar_osken_controller.py --verbose

See Also:
    dijkstra_osken_controller.py        - same metric, exhaustive search
    astar_multipath_osken_controller.py - adds ECMP over equal-cost paths
"""

import os
import sys

from base_controller import SPFBaseController
from algorithms.astar import astar, build_reverse_hop_heuristic
from algorithms.weight_utils import build_directed_metric_dict, load_link_metrics, bandwidth_to_costs

# Module-level exports used by astar_multipath_osken_controller.py
ASTAR_FLOW_COOKIE = 0x4153545200000001
ASTAR_FLOW_COOKIE_MASK = 0xFFFFFFFFFFFFFFFF
ASTAR_FLOW_PRIORITY = 100

WEIGHTS_FILE = os.environ.get(
    "SPF_WEIGHTS_FILE",
    os.path.join(os.path.dirname(__file__), "link_weights.json"),
)
WEIGHT_FIELD = os.environ.get("SPF_WEIGHT_FIELD", "bandwidth_mbps")
REF_BANDWIDTH = float(os.environ.get("SPF_REF_BANDWIDTH", "1000"))


def _load_weights(path):
    """Load link weights from JSON; return {} if file is absent or malformed."""
    return load_link_metrics(path, WEIGHT_FIELD)


class AStarSwitch(SPFBaseController):
    """Single shortest-path forwarding using A* heuristic search.

    Adds a per-destination heuristic cache on top of SPFBaseController.
    The heuristic (reverse-BFS hop distance) is computed once per topology
    change and reused for all (*, dst) queries.
    """

    FLOW_COOKIE = ASTAR_FLOW_COOKIE

    def __init__(self, *args, **kwargs):
        super(AStarSwitch, self).__init__(*args, **kwargs)
        # Cache: dst -> {node: hop_distance_to_dst}
        # Invalidated whenever the topology changes.
        self.heuristic_hop_cache = {}
        raw_weights = _load_weights(WEIGHTS_FILE)
        if raw_weights:
            self.logger.info("[ASTAR-WEIGHTS] loaded %d link weights from %s",
                             len(raw_weights), WEIGHTS_FILE)
        else:
            self.logger.info("[ASTAR-WEIGHTS] no weight file; using hop-count metric")

    def _build_weight_dict(self):
        """Build weights dict keyed by (u, v) from the current adjacency.

        The JSON file is reloaded for each query so weight changes are picked
        up dynamically.
        """
        link_weights = _load_weights(WEIGHTS_FILE)
        if not link_weights:
            return None
        directed = build_directed_metric_dict(self.adjacency, link_weights)
        if WEIGHT_FIELD == "bandwidth_mbps":
            return bandwidth_to_costs(directed, ref_bandwidth=REF_BANDWIDTH)
        return directed

    def _on_topology_changed(self):
        """Clear heuristic cache so stale hop-distances are not reused."""
        self.heuristic_hop_cache.clear()
        self.logger.debug("[A*-CACHE] heuristic cache cleared after topology change")

    def compute_path(self, src, dst, first_port, final_port):
        """Compute shortest path using A* with reverse-BFS hop heuristic.

        Algorithm steps:
            1. Build/reuse heuristic: reverse-BFS from dst gives h(v) for each v
            2. Run A* guided by h(v) - visits fewer nodes than Dijkstra
            3. Reconstruct path by following predecessor pointers
        """
        self.logger.debug("[PATH-QUERY] A*: s%d -> s%d", src, dst)

        # --- Phase 1: Get or compute heuristic for this destination ---
        # h[v] = lower-bound cost estimate from v to dst.
        # For hop-count routing we use reverse BFS. For weighted routing
        # (e.g. delay_ms) we fall back to zero heuristic to preserve admissibility.
        if WEIGHT_FIELD == "bandwidth_mbps":
            if dst not in self.heuristic_hop_cache:
                self.heuristic_hop_cache[dst] = build_reverse_hop_heuristic(
                    self.adjacency, dst
                )
                self.logger.debug(
                    "[A*-CACHE] built heuristic for dst=s%d size=%d",
                    dst, len(self.heuristic_hop_cache[dst]),
                )
            heuristic = self.heuristic_hop_cache[dst]
        else:
            heuristic = {node: 0 for node in self.adjacency}
            heuristic[dst] = 0
            self.logger.debug("[A*-HEURISTIC] weighted metric=%s, using zero heuristic",
                              WEIGHT_FIELD)

        # --- Phase 2: Run A* from src guided by heuristic ---
        # distance[v] = g(v): actual shortest hop count from src to v
        # previous[v]:        predecessor on the shortest path
        weights = self._build_weight_dict()
        distance, previous = astar(self.adjacency, src, dst, heuristic, weights=weights)

        reachable = sum(1 for d in distance.values() if d != float("inf"))
        self.logger.info("[SPF-DONE] A* s%d->s%d reachable=%d/%d",
                         src, dst, reachable, len(distance))

        # --- Phase 3: Reconstruct path from predecessor pointers ---
        return self._reconstruct_path(src, dst, first_port, final_port, distance, previous)

    def stop(self):
        self.heuristic_hop_cache.clear()
        super(AStarSwitch, self).stop()


if __name__ == '__main__':
    current_file = os.path.abspath(__file__)
    passthrough_args = sys.argv[1:]
    if '--observe-links' not in passthrough_args:
        passthrough_args = ['--observe-links'] + passthrough_args
    sys.argv = ['astar_osken_controller', *passthrough_args, current_file]
    from os_ken.cmd.manager import main
    sys.exit(main())
