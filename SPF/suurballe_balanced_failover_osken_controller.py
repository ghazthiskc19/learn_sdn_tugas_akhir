"""Suurballe balanced failover OpenFlow controller.

Computes two edge-disjoint shortest paths using Suurballe's algorithm, then
installs two FAST_FAILOVER groups (one per primary port) and a SELECT group
that load-balances across them. If a primary port fails, the corresponding
FAST_FAILOVER group falls back to the other port.

Complexity:   O((V+E) log V) per (src, dst) pair
Metric:       hop count
Multipath:    two disjoint paths (primary + backup)
ECMP:         yes (SELECT group for load balancing)
"""

import os
import sys

from os_ken.controller import ofp_event
from os_ken.controller.handler import MAIN_DISPATCHER
from os_ken.controller.handler import set_ev_cls
from os_ken.lib.packet import ethernet, ether_types, packet

from base_controller import SPFBaseController
from algorithms.suurballe import suurballe_edge_disjoint
from algorithms.group_ids import alloc_group_id_triple

BAL_FLOW_COOKIE = 0x5342414C00000001   # "SBAL" in hex
BAL_FLOW_COOKIE_MASK = 0xFFFFFFFFFFFFFFFF
BAL_FLOW_PRIORITY = 100
GROUP_ID_SPACE = 0x7FFFFFFF


class SuurballeBalancedFailoverSwitch(SPFBaseController):
    """Edge-disjoint load balancing with first-hop fast failover."""

    FLOW_COOKIE = BAL_FLOW_COOKIE

    def __init__(self, *args, **kwargs):
        super(SuurballeBalancedFailoverSwitch, self).__init__(*args, **kwargs)
        self.path_cache = {}
        # (src_mac, dst_mac) -> (ingress_dpid, select_gid, ff_gid_a, ff_gid_b)
        self.flow_groups = {}

    # ------------------------------------------------------------------
    # Group management
    # ------------------------------------------------------------------

    def _alloc_group_ids(self, src_mac, dst_mac):
        key = (src_mac, dst_mac)
        existing = self.flow_groups.get(key)
        if existing is not None:
            return existing[1], existing[2], existing[3]

        used = set()
        for _, select_gid, ff_gid_a, ff_gid_b in self.flow_groups.values():
            used.update([select_gid, ff_gid_a, ff_gid_b])

        seed = f"{src_mac}->{dst_mac}"
        return alloc_group_id_triple(seed, used_ids=used, space=GROUP_ID_SPACE)

    def _install_group_flow(self, datapath, in_port, src_mac, dst_mac, group_id):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch(in_port=in_port, eth_src=src_mac, eth_dst=dst_mac)
        actions = [parser.OFPActionGroup(group_id)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            cookie=BAL_FLOW_COOKIE,
            cookie_mask=BAL_FLOW_COOKIE_MASK,
            command=ofproto.OFPFC_DELETE_STRICT,
            out_port=ofproto.OFPP_ANY,
            out_group=ofproto.OFPG_ANY,
            priority=BAL_FLOW_PRIORITY,
            match=match,
        ))
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath,
            cookie=BAL_FLOW_COOKIE,
            command=ofproto.OFPFC_ADD,
            idle_timeout=0,
            hard_timeout=0,
            priority=BAL_FLOW_PRIORITY,
            match=match,
            instructions=inst,
        ))

    def _install_fast_failover_group(self, datapath, group_id, primary_port, backup_port):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        ports = [primary_port]
        if backup_port is not None and backup_port != primary_port:
            ports.append(backup_port)

        if not ports:
            return False

        buckets = [
            parser.OFPBucket(
                weight=0,
                watch_port=p,
                watch_group=ofproto.OFPG_ANY,
                actions=[parser.OFPActionOutput(p)],
            )
            for p in ports
        ]

        datapath.send_msg(parser.OFPGroupMod(
            datapath=datapath,
            command=ofproto.OFPGC_DELETE,
            type_=ofproto.OFPGT_FF,
            group_id=group_id,
            buckets=[],
        ))
        datapath.send_msg(parser.OFPGroupMod(
            datapath=datapath,
            command=ofproto.OFPGC_ADD,
            type_=ofproto.OFPGT_FF,
            group_id=group_id,
            buckets=buckets,
        ))
        return True

    def _install_select_group(self, datapath, group_id, ff_gid_a, ff_gid_b):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        buckets = [
            parser.OFPBucket(
                weight=1,
                watch_port=ofproto.OFPP_ANY,
                watch_group=ofproto.OFPG_ANY,
                actions=[parser.OFPActionGroup(ff_gid_a)],
            ),
            parser.OFPBucket(
                weight=1,
                watch_port=ofproto.OFPP_ANY,
                watch_group=ofproto.OFPG_ANY,
                actions=[parser.OFPActionGroup(ff_gid_b)],
            ),
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
        return True

    def _delete_group(self, datapath, group_id, group_type):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        datapath.send_msg(parser.OFPGroupMod(
            datapath=datapath,
            command=ofproto.OFPGC_DELETE,
            type_=group_type,
            group_id=group_id,
            buckets=[],
        ))

    def _delete_balanced_groups(self, datapath):
        for dpid, select_gid, ff_gid_a, ff_gid_b in self.flow_groups.values():
            if dpid != datapath.id:
                continue
            self._delete_group(datapath, select_gid, datapath.ofproto.OFPGT_SELECT)
            self._delete_group(datapath, ff_gid_a, datapath.ofproto.OFPGT_FF)
            self._delete_group(datapath, ff_gid_b, datapath.ofproto.OFPGT_FF)

    # ------------------------------------------------------------------
    # Path computation
    # ------------------------------------------------------------------

    def _decorate_path(self, node_path, first_port, final_port):
        if not node_path:
            return []
        if len(node_path) == 1:
            return [(node_path[0], first_port, final_port)]

        result = []
        in_port = first_port
        for s1, s2 in zip(node_path[:-1], node_path[1:]):
            out_port = self._get_port(s1, s2)
            if out_port is None:
                self.logger.error("[PATH-PORTMAP] s%d->s%d missing port", s1, s2)
                return []
            result.append((s1, in_port, out_port))
            in_port = self._get_port(s2, s1)
            if in_port is None and s2 != node_path[-1]:
                self.logger.error("[PATH-PORTMAP] s%d->s%d reverse port missing", s2, s1)
                return []
        result.append((node_path[-1], in_port, final_port))
        return result

    def compute_disjoint_paths(self, src, dst, first_port, final_port):
        if src not in self.switches or dst not in self.switches:
            return []
        if src == dst:
            return [[(src, first_port, final_port)]]

        cache_key = (src, dst)
        if cache_key in self.path_cache:
            node_paths = self.path_cache[cache_key]
        else:
            node_paths = suurballe_edge_disjoint(self.adjacency, src, dst)
            self.path_cache[cache_key] = node_paths
            self.logger.info("[PATH-SUUR] s%d->s%d paths=%d", src, dst, len(node_paths))

        return [d for p in node_paths
                for d in [self._decorate_path(p, first_port, final_port)] if d]

    def compute_path(self, src, dst, first_port, final_port):
        paths = self.compute_disjoint_paths(src, dst, first_port, final_port)
        return paths[0] if paths else []

    # ------------------------------------------------------------------
    # Installation
    # ------------------------------------------------------------------

    def install_balanced_failover(self, paths, src_mac, dst_mac):
        if not paths:
            return

        key = (src_mac, dst_mac)
        if self.installed_paths.get(key) == paths:
            return

        ingress_dpid = paths[0][0][0]
        ingress_in_port = paths[0][0][1]
        ingress_dp = self.datapaths.get(ingress_dpid)
        if ingress_dp is None:
            self.logger.warning("[BF-INSTALL] s%d datapath unavailable", ingress_dpid)
            return

        if len(paths) == 1:
            for sw, in_p, out_p in paths[0]:
                dp = self.datapaths.get(sw)
                if dp:
                    self._install_unicast_flow(dp, in_p, out_p, src_mac, dst_mac)
            existing = self.flow_groups.pop(key, None)
            if existing:
                dp = self.datapaths.get(existing[0])
                if dp:
                    self._delete_balanced_groups(dp)
            self.installed_paths[key] = paths
            return

        primary_port = paths[0][0][2]
        backup_port = paths[1][0][2]
        if primary_port == backup_port:
            for sw, in_p, out_p in paths[0]:
                dp = self.datapaths.get(sw)
                if dp:
                    self._install_unicast_flow(dp, in_p, out_p, src_mac, dst_mac)
            self.installed_paths[key] = [paths[0]]
            return

        # Transit and egress hops: deterministic unicast flows
        for path in paths:
            for sw, in_p, out_p in path[1:]:
                dp = self.datapaths.get(sw)
                if dp:
                    self._install_unicast_flow(dp, in_p, out_p, src_mac, dst_mac)

        select_gid, ff_gid_a, ff_gid_b = self._alloc_group_ids(src_mac, dst_mac)
        if self._install_fast_failover_group(ingress_dp, ff_gid_a, primary_port, backup_port) and \
           self._install_fast_failover_group(ingress_dp, ff_gid_b, backup_port, primary_port) and \
           self._install_select_group(ingress_dp, select_gid, ff_gid_a, ff_gid_b):
            self.flow_groups[key] = (ingress_dpid, select_gid, ff_gid_a, ff_gid_b)
            self._install_group_flow(ingress_dp, ingress_in_port, src_mac, dst_mac, select_gid)
            self.logger.info(
                "[BF-INSTALL] %s->%s paths=%d ingress=s%d select=%d ff_a=%d ff_b=%d",
                src_mac, dst_mac, len(paths), ingress_dpid, select_gid, ff_gid_a, ff_gid_b
            )
            self.installed_paths[key] = paths
        else:
            for sw, in_p, out_p in paths[0]:
                dp = self.datapaths.get(sw)
                if dp:
                    self._install_unicast_flow(dp, in_p, out_p, src_mac, dst_mac)
            self.installed_paths[key] = [paths[0]]

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def _on_topology_changed(self):
        self.path_cache.clear()

    def _flush_all_flows(self):
        for dp in self.datapaths.values():
            self._delete_all_flows(dp)
            self._delete_balanced_groups(dp)
        self.installed_paths.clear()
        self.path_cache.clear()
        self.flow_groups.clear()

    def _reinstall_all_known_routes(self):
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
                paths = self.compute_disjoint_paths(
                    src_loc[0], dst_loc[0], src_loc[1], dst_loc[1]
                )
                if paths:
                    self.install_balanced_failover(paths, src_mac, dst_mac)
                    installed += 1
                else:
                    unreachable += 1
        self.logger.info(
            "[TOPO] balanced failover refresh: installed=%d skipped=%d unreachable=%d hosts=%d",
            installed, skipped, unreachable, len(hosts)
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
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
                paths = self.compute_disjoint_paths(src_sw, dst_sw, src_port, dst_port)
                if paths:
                    self.install_balanced_failover(paths, src, dst)
                else:
                    self.logger.warning("[PKT-DROP] %s->%s: no balanced failover path", src, dst)
                    return

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

            self.logger.warning("[PKT-DROP] %s->%s: s%d not in balanced failover path", src, dst, dpid)
        else:
            self._flood_over_tree(dp, in_port, msg.data, msg.buffer_id)

    def stop(self):
        self.path_cache.clear()
        self.flow_groups.clear()
        super(SuurballeBalancedFailoverSwitch, self).stop()


if __name__ == '__main__':
    current_file = os.path.abspath(__file__)
    passthrough_args = sys.argv[1:]
    if '--observe-links' not in passthrough_args:
        passthrough_args = ['--observe-links'] + passthrough_args
    sys.argv = ['suurballe_balanced_failover_osken_controller', *passthrough_args, current_file]
    from os_ken.cmd.manager import main
    sys.exit(main())
