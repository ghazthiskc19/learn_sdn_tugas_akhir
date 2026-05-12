"""K-Shortest Paths OpenFlow controller using Yen's algorithm.

Computes K distinct shortest paths per (src, dst) pair using Yen's algorithm,
then installs an OpenFlow SELECT group on the ingress switch to distribute
traffic across all paths (ECMP load balancing).

Complexity:   O(K * V * (E + V log V)) per (src, dst) pair
Metric:       hop count (all edges weight 1)
Paths:        up to K_PATHS distinct shortest or near-shortest paths
ECMP:         yes - OpenFlow SELECT group on ingress switch

Run:
    python3 kshortest_osken_controller.py

See Also:
    dijkstra_multipath_osken_controller.py - equal-cost only (no spur nodes)
    astar_multipath_osken_controller.py    - A* guided multipath
"""

import hashlib
import os
import sys

from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.lib.packet import ethernet, ether_types, packet

from base_controller import SPFBaseController
from algorithms.yen_k_shortest import yen_k_shortest

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

K_SHORTEST_COOKIE = 0x4B53500000000001   # "KSP\0" in hex
K_SHORTEST_COOKIE_MASK = 0xFFFFFFFFFFFFFFFF
K_SHORTEST_PRIORITY = 100
K_PATHS = 2               # Number of paths to compute per host pair
GROUP_ID_SPACE = 0x7FFFFFFF


class KShortestPathsController(SPFBaseController):
    """K-shortest paths controller with ECMP load balancing.

    Uses Yen's algorithm to find K shortest simple paths, then installs
    an OpenFlow SELECT group so the switch hardware chooses among next hops.

    Yen's algorithm vs equal-cost multipath (dijkstra_multi_parent):
        - dijkstra_multi_parent: only equal-hop-count paths
        - Yen's algorithm: K paths in non-decreasing order of cost (may differ)
        - For K=2 on hop-metric, both often yield the same result;
          Yen's shines when you want path diversity (different segments)

    Inherits all infrastructure from SPFBaseController; overrides only
    the path installation and packet-in handler to apply ECMP logic.
    """

    FLOW_COOKIE = K_SHORTEST_COOKIE

    def __init__(self, *args, **kwargs):
        super(KShortestPathsController, self).__init__(*args, **kwargs)
        self.path_cache = {}    # (src, dst, K) -> [node_path, ...]
        self.flow_groups = {}   # (src_mac, dst_mac) -> (ingress_dpid, group_id)

    # ─────────────────────────────────────────────────────────────────────────
    # ECMP group management
    # ─────────────────────────────────────────────────────────────────────────

    def _alloc_group_id(self, src_mac, dst_mac):
        """Allocate a deterministic group-id with collision avoidance."""
        key = (src_mac, dst_mac)
        existing = self.flow_groups.get(key)
        if existing is not None:
            return existing[1]
        seed = f"{src_mac}->{dst_mac}".encode()
        candidate = int(hashlib.md5(seed).hexdigest()[:8], 16) & GROUP_ID_SPACE
        if candidate == 0:
            candidate = 1
        used_ids = {gid for _, gid in self.flow_groups.values()}
        while candidate in used_ids:
            candidate = (candidate % GROUP_ID_SPACE) + 1
        return candidate

    def _install_group_flow(self, datapath, in_port, src_mac, dst_mac, group_id):
        """Install ingress flow forwarding to SELECT group."""
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(in_port=in_port, eth_src=src_mac, eth_dst=dst_mac)
        actions = [parser.OFPActionGroup(group_id)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            cookie=K_SHORTEST_COOKIE,
            cookie_mask=K_SHORTEST_COOKIE_MASK,
            command=ofproto.OFPFC_DELETE_STRICT,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=K_SHORTEST_PRIORITY,
            match=match,
        ))
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            cookie=K_SHORTEST_COOKIE,
            command=ofproto.OFPFC_ADD,
            idle_timeout=0,
            hard_timeout=0,
            priority=K_SHORTEST_PRIORITY,
            match=match,
            instructions=inst,
        ))

    def _install_select_group(self, datapath, group_id, out_ports):
        """Install or replace OpenFlow SELECT group (one bucket per next-hop)."""
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        unique_ports = sorted(set(out_ports))
        if not unique_ports:
            return False
        buckets = [
            parser.OFPBucket(
                weight=1,
                watch_port=ofproto.OFPP_ANY,
                watch_group=ofproto.OFPG_ANY,
                actions=[parser.OFPActionOutput(p)],
            )
            for p in unique_ports
        ]
        datapath.send_msg(parser.OFPGroupMod(
            datapath=datapath,
            command=ofproto.OFPGC_DELETE,
            type_=ofproto.OFPGT_SELECT,
            group_id=group_id,
            buckets=[],
        ))
        datapath.send_msg(parser.OFPGroupMod(
            datapath=datapath,
            command=ofproto.OFPGC_ADD,
            type_=ofproto.OFPGT_SELECT,
            group_id=group_id,
            buckets=buckets,
        ))
        self.logger.debug("[ECMP-GROUP] s%d group=%d ports=%s",
                          datapath.id, group_id, unique_ports)
        return True

    def _delete_ksp_groups(self, datapath):
        """Delete all ECMP groups installed on a datapath."""
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        gids = {gid for dpid, gid in self.flow_groups.values() if dpid == datapath.id}
        for gid in gids:
            datapath.send_msg(parser.OFPGroupMod(
                datapath=datapath,
                command=ofproto.OFPGC_DELETE,
                type_=ofproto.OFPGT_SELECT,
                group_id=gid,
                buckets=[],
            ))

    # ─────────────────────────────────────────────────────────────────────────
    # Path computation (Yen's K-shortest)
    # ─────────────────────────────────────────────────────────────────────────

    def _decorate_path(self, node_path, first_port, final_port):
        """Convert a node-list path to [(dpid, in_port, out_port), ...] tuples."""
        if not node_path:
            return []
        if len(node_path) == 1:
            return [(node_path[0], first_port, final_port)]
        result = []
        in_port = first_port
        for s1, s2 in zip(node_path[:-1], node_path[1:]):
            out_port = self._get_port(s1, s2)
            if out_port is None:
                self.logger.error("[PATH-PORTMAP] s%d->s%d: port missing", s1, s2)
                return []
            result.append((s1, in_port, out_port))
            in_port = self._get_port(s2, s1)
            if in_port is None and s2 != node_path[-1]:
                self.logger.error("[PATH-PORTMAP] s%d->s%d: reverse port missing", s2, s1)
                return []
        result.append((node_path[-1], in_port, final_port))
        return result

    def compute_k_shortest_paths(self, src, dst, first_port, final_port, k=K_PATHS):
        """Return up to k decorated shortest paths using Yen's algorithm.

        Yen's algorithm enumerates simple paths in non-decreasing cost order.
        Paths are cached by (src, dst, k) and reused until topology changes.

        Algorithm steps:
            1. Check cache — return cached node-paths if valid
            2. Call yen_k_shortest(adjacency, src, dst, k) from algorithms/
            3. Decorate each node-path with (dpid, in_port, out_port) tuples
        """
        if src not in self.switches or dst not in self.switches:
            return []
        if src == dst:
            return [[(src, first_port, final_port)]]

        # --- Phase 1: Check path cache ---
        cache_key = (src, dst, k)
        if cache_key in self.path_cache:
            node_paths = self.path_cache[cache_key]
            self.logger.debug("[PATH-CACHE] KSP hit s%d->s%d k=%d", src, dst, k)
        else:
            # --- Phase 2: Run Yen's K-shortest paths ---
            # Returns [path1, path2, ...] where each path is a list of DPIDs
            node_paths = yen_k_shortest(self.adjacency, src, dst, k)
            self.path_cache[cache_key] = node_paths
            self.logger.info("[PATH-KSP] s%d->s%d k=%d found=%d",
                             src, dst, k, len(node_paths))

        # --- Phase 3: Decorate each node-path with port numbers ---
        return [d for np in node_paths[:k]
                for d in [self._decorate_path(np, first_port, final_port)] if d]

    def compute_path(self, src, dst, first_port, final_port):
        """Single-path compute_path contract: return the best (first) K-shortest path."""
        paths = self.compute_k_shortest_paths(src, dst, first_port, final_port, k=1)
        return paths[0] if paths else []

    # ─────────────────────────────────────────────────────────────────────────
    # ECMP installation
    # ─────────────────────────────────────────────────────────────────────────

    def install_k_paths(self, paths, src_mac, dst_mac):
        """Install K-path ECMP: SELECT group on ingress, unicast on transit."""
        if not paths:
            return
        key = (src_mac, dst_mac)
        if self.installed_paths.get(key) == paths:
            return

        ingress_dpid = paths[0][0][0]
        ingress_in_port = paths[0][0][1]
        ingress_out_ports = [p[0][2] for p in paths if p and p[0][0] == ingress_dpid]

        ingress_dp = self.datapaths.get(ingress_dpid)
        if ingress_dp is None:
            self.logger.warning("[KSP-INSTALL] s%d datapath unavailable", ingress_dpid)
            return

        # Transit/egress hops: deterministic unicast flows
        for path in paths:
            for sw, in_p, out_p in path[1:]:
                dp = self.datapaths.get(sw)
                if dp:
                    self._install_unicast_flow(dp, in_p, out_p, src_mac, dst_mac)

        group_id = self._alloc_group_id(src_mac, dst_mac)
        if self._install_select_group(ingress_dp, group_id, ingress_out_ports):
            self.flow_groups[key] = (ingress_dpid, group_id)
            self._install_group_flow(ingress_dp, ingress_in_port, src_mac, dst_mac, group_id)
            self.logger.info("[KSP-INSTALL] %s->%s paths=%d ingress=s%d group=%d",
                             src_mac, dst_mac, len(paths), ingress_dpid, group_id)
            self.installed_paths[key] = paths

    # ─────────────────────────────────────────────────────────────────────────
    # Overrides
    # ─────────────────────────────────────────────────────────────────────────

    def _on_topology_changed(self):
        """Clear path cache on topology changes so stale paths are not reused."""
        self.path_cache.clear()
        self.logger.debug("[KSP-CACHE] path cache cleared after topology change")

    def _flush_all_flows(self):
        """Flush flows AND delete all ECMP groups."""
        for dp in self.datapaths.values():
            self._delete_all_flows(dp)
            self._delete_ksp_groups(dp)
        self.installed_paths.clear()
        self.path_cache.clear()
        self.flow_groups.clear()

    def _reinstall_all_known_routes(self):
        """Reinstall K-path ECMP routes for all known host pairs."""
        hosts = self._active_hosts()
        installed = skipped = unreachable = 0
        for src_mac in hosts:
            for dst_mac in hosts:
                if src_mac == dst_mac:
                    continue
                src_loc = self.mymacs.get(src_mac)
                dst_loc = self.mymacs.get(dst_mac)
                if not src_loc or not dst_loc:
                    skipped += 1
                    continue
                paths = self.compute_k_shortest_paths(
                    src_loc[0], dst_loc[0], src_loc[1], dst_loc[1]
                )
                if paths:
                    self.install_k_paths(paths, src_mac, dst_mac)
                    installed += 1
                else:
                    unreachable += 1
        self.logger.info(
            "[TOPO] KSP refresh: installed=%d skipped=%d unreachable=%d hosts=%d",
            installed, skipped, unreachable, len(hosts)
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """Handle packet-in; install K-path ECMP or flood."""
        msg = ev.msg
        dp = msg.datapath
        ofproto = dp.ofproto
        parser = dp.ofproto_parser
        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src, dst, dpid = eth.src, eth.dst, dp.id

        if self._is_access_port(dpid, in_port):
            self._update_host_location(src, dpid, in_port)

        if src not in self.mymacs:
            return

        if dst in self.mymacs:
            key = (src, dst)
            if key in self.installed_paths:
                paths = self.installed_paths[key]
            else:
                src_sw, src_port = self.mymacs[src]
                dst_sw, dst_port = self.mymacs[dst]
                paths = self.compute_k_shortest_paths(src_sw, dst_sw, src_port, dst_port)
                if paths:
                    self.install_k_paths(paths, src, dst)
                else:
                    self.logger.warning("[PKT-DROP] %s->%s: no K-shortest path found",
                                        src, dst)
                    return

            # Try deterministic unicast output port (transit/egress switch)
            out_port = next((p for sw, _, p in paths[0] if sw == dpid), None)
            if out_port is not None:
                data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
                dp.send_msg(parser.OFPPacketOut(
                    datapath=dp, buffer_id=msg.buffer_id,
                    in_port=in_port,
                    actions=[parser.OFPActionOutput(out_port)],
                    data=data,
                ))
                return

            # Fallback: ingress switch uses SELECT group
            group_info = self.flow_groups.get((src, dst))
            if group_info and group_info[0] == dpid:
                data = msg.data if msg.buffer_id == ofproto.OFP_NO_BUFFER else None
                dp.send_msg(parser.OFPPacketOut(
                    datapath=dp, buffer_id=msg.buffer_id,
                    in_port=in_port,
                    actions=[parser.OFPActionGroup(group_info[1])],
                    data=data,
                ))
                return

            self.logger.warning("[PKT-DROP] %s->%s: s%d not in any K-path", src, dst, dpid)
        else:
            self._flood_over_tree(dp, in_port, msg.data, msg.buffer_id)

    def stop(self):
        self.path_cache.clear()
        self.flow_groups.clear()
        super(KShortestPathsController, self).stop()


if __name__ == '__main__':
    current_file = os.path.abspath(__file__)
    passthrough_args = sys.argv[1:]
    if '--observe-links' not in passthrough_args:
        passthrough_args = ['--observe-links'] + passthrough_args
    sys.argv = ['kshortest_osken_controller', *passthrough_args, current_file]
    from os_ken.cmd.manager import main
    sys.exit(main())
