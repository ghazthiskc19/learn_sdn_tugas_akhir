#!/usr/bin/env python3
"""
Mesh-specific hop count experiment.

Hop count is estimated by counting how many switches install flow rules
that match the source and destination host MAC addresses.
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from functools import partial

from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.topo import Topo
from mininet.util import dumpNodeConnections


class MeshTopo(Topo):
    def addSwitch(self, name, **opts):
        kwargs = {"protocols": "OpenFlow13"}
        kwargs.update(opts)
        if "dpid" not in kwargs:
            kwargs["dpid"] = f"{self._next_dpid:016x}"
            self._next_dpid += 1
        return super(MeshTopo, self).addSwitch(name, **kwargs)

    def __init__(self):
        Topo.__init__(self)
        self._next_dpid = 1

        info("*** Adding hosts\n")
        host_a1 = self.addHost("HostA1", ip="10.0.0.1/24")
        host_a2 = self.addHost("HostA2", ip="10.0.0.2/24")
        host_b1 = self.addHost("HostB1", ip="10.0.0.3/24")
        host_b2 = self.addHost("HostB2", ip="10.0.0.4/24")
        host_d1 = self.addHost("HostD1", ip="10.0.0.5/24")
        host_d2 = self.addHost("HostD2", ip="10.0.0.6/24")
        host_e1 = self.addHost("HostE1", ip="10.0.0.7/24")
        host_e2 = self.addHost("HostE2", ip="10.0.0.8/24")

        info("*** Adding switches\n")
        switch_a = self.addSwitch("SwitchA")
        switch_b = self.addSwitch("SwitchB")
        switch_c = self.addSwitch("SwitchC")
        switch_d = self.addSwitch("SwitchD")
        switch_e = self.addSwitch("SwitchE")
        switch_f = self.addSwitch("SwitchF")

        info("*** Adding host links\n")
        self.addLink(host_a1, switch_a, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_a2, switch_a, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_b1, switch_b, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_b2, switch_b, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_d1, switch_d, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_d2, switch_d, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_e1, switch_e, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_e2, switch_e, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)

        info("*** Adding switch links\n")
        self.addLink(switch_a, switch_b, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_c, port1=4, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_d, port1=5, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_e, port1=6, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_f, port1=7, port2=3, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_b, switch_c, port1=4, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_d, port1=5, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_e, port1=6, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_f, port1=7, port2=4, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_c, switch_d, port1=5, port2=5, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_c, switch_e, port1=6, port2=5, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_c, switch_f, port1=7, port2=5, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_d, switch_e, port1=6, port2=6, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_d, switch_f, port1=7, port2=6, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_e, switch_f, port1=7, port2=7, bw=500, delay='1ms', use_hfsc=True)


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
ROOT_SCRIPTS = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
if ROOT_SCRIPTS not in sys.path:
    sys.path.insert(0, ROOT_SCRIPTS)


def start_controller(cmd):
    if not cmd:
        return None
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    return proc


def stop_controller(proc):
    if not proc:
        return
    try:
        proc.terminate()
        proc.wait(timeout=3)
    except Exception:
        proc.kill()


def build_network():
    topo = MeshTopo()
    net = Mininet(
        topo=topo,
        controller=partial(RemoteController, ip='127.0.0.1', port=6633),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        waitConnected=True,
    )
    return net


def disable_ipv6(net):
    info("\n*** Disabling IPv6\n")
    for host in net.hosts:
        host.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1 || true')
    for sw in net.switches:
        sw.cmd('sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1 || true')


def clear_switch_flows(net):
    for sw in net.switches:
        try:
            sw.cmd(f'ovs-ofctl del-flows {sw.name}')
        except Exception:
            pass


def kill_iperf_everywhere(net):
    for host in net.hosts:
        try:
            host.cmd('killall -9 iperf 2>/dev/null || true')
        except Exception:
            pass


def restore_links(net):
    link_pairs = [
        ('SwitchA', 'SwitchB'), ('SwitchA', 'SwitchC'), ('SwitchA', 'SwitchD'), ('SwitchA', 'SwitchE'), ('SwitchA', 'SwitchF'),
        ('SwitchB', 'SwitchC'), ('SwitchB', 'SwitchD'), ('SwitchB', 'SwitchE'), ('SwitchB', 'SwitchF'),
        ('SwitchC', 'SwitchD'), ('SwitchC', 'SwitchE'), ('SwitchC', 'SwitchF'),
        ('SwitchD', 'SwitchE'), ('SwitchD', 'SwitchF'),
        ('SwitchE', 'SwitchF'),
    ]
    for left, right in link_pairs:
        try:
            net.configLinkStatus(left, right, 'up')
        except Exception:
            pass


def get_hop_count(net, src_host, dst_host, verbose=False):
    """Count switches that install flows matching both host MAC addresses."""
    mac_src = src_host.MAC()
    mac_dst = dst_host.MAC()

    clear_switch_flows(net)
    time.sleep(1)
    src_host.cmd(f'ping -c 1 -W 1 {dst_host.IP()}')
    time.sleep(0.5)

    counter = 0
    for sw in net.switches:
        try:
            output = sw.cmd(f'ovs-ofctl dump-flows {sw.name}')
        except Exception:
            output = ''
        output_lower = output.lower()
        if f'dl_src={mac_src.lower()}' in output_lower and f'dl_dst={mac_dst.lower()}' in output_lower:
            counter += 1
            if verbose:
                print(f'Match on {sw.name}')

    return counter


def normalize_algo_name(value):
    if not value:
        return "unknown"
    return value.strip().replace(" ", "_").replace("-", "_").lower()


def infer_algo_name(controller_cmd):
    if not controller_cmd:
        return None
    for token in str(controller_cmd).split():
        if token.endswith("_osken_controller.py"):
            return os.path.basename(token).replace("_osken_controller.py", "")
    return None


def build_csv_name(algo_name, metric_name, scenario_idx):
    algo_name = normalize_algo_name(algo_name)
    metric_name = normalize_algo_name(metric_name)
    return f"{algo_name}_{metric_name}_{scenario_idx}.csv"


def save_results(rows, output_dir='results/mesh/hopcount', algo_name='unknown', metric_name='hopcount'):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))
    fieldnames = sorted({key for row in rows for key in row.keys()})
    ordered = ['scenario'] + [key for key in fieldnames if key != 'scenario']
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ordered)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return csv_path


def save_per_scenario_csvs(rows, output_dir='results/mesh/hopcount', algo_name='unknown', metric_name='hopcount'):
    os.makedirs(output_dir, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    ordered = ['scenario'] + [key for key in fieldnames if key != 'scenario']
    paths = []
    for idx, row in enumerate(rows, 1):
        path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, idx))
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=ordered)
            writer.writeheader()
            writer.writerow(row)
        paths.append(path)
    return paths


def run_baseline(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    value = get_hop_count(net, host_a1, host_e1, verbose=verbose)
    print(f'Hop Baseline: {value}')
    return {'scenario': 'Hop Baseline', 'hop_count': value, 'status': 'SUCCESS' if value is not None else 'TIMEOUT'}


def run_direct_failure(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    net.configLinkStatus('SwitchA', 'SwitchE', 'down')
    time.sleep(1)
    value = get_hop_count(net, host_a1, host_e1, verbose=verbose)
    print(f'Hop Direct Failure: {value}')
    return {'scenario': 'Hop Direct Failure', 'hop_count': value, 'status': 'SUCCESS' if value is not None else 'TIMEOUT'}


def run_restricted_path(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    time.sleep(2)
    net.configLinkStatus('SwitchA', 'SwitchB', 'down')
    net.configLinkStatus('SwitchA', 'SwitchC', 'down')
    net.configLinkStatus('SwitchA', 'SwitchD', 'down')
    net.configLinkStatus('SwitchF', 'SwitchE', 'down')
    time.sleep(1)
    value = get_hop_count(net, host_a1, host_e1, verbose=verbose)
    print(f'Hop Restricted Path: {value}')
    return {'scenario': 'Hop Restricted Path', 'hop_count': value, 'status': 'SUCCESS' if value is not None else 'TIMEOUT'}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Hop Count Measurement Experiment (Mesh Topology)')
    parser.add_argument('--controller-cmd', help='Controller command to start', default=None)
    parser.add_argument('--algo-name', help='Algorithm label for CSV filenames (e.g., dijkstra, astar)', default=None)
    parser.add_argument('--output-dir', help='Output directory for results', default='results/mesh/hopcount')
    parser.add_argument('--no-controller', help='Do not auto-start controller', action='store_true')
    parser.add_argument('--verbose', help='Verbose logging', action='store_true')
    args = parser.parse_args(argv)
    metric_name = 'hopcount'
    algo_name = normalize_algo_name(args.algo_name or infer_algo_name(args.controller_cmd))

    ctrl_proc = None
    if not args.no_controller and args.controller_cmd:
        ctrl_proc = start_controller(args.controller_cmd)

    net = build_network()
    try:
        disable_ipv6(net)
        net.start()
        dumpNodeConnections(net.hosts)

        hosts = {host.name: host for host in net.hosts}
        results = []

        print('\n' + '=' * 72)
        print('SKENARIO 1: Baseline (Direct Link Routing)')
        print('=' * 72)
        results.append(run_baseline(net, hosts, verbose=args.verbose))

        print('\n' + '=' * 72)
        print('SKENARIO 2: Direct Link Failure (1-Hop Transit)')
        print('=' * 72)
        results.append(run_direct_failure(net, hosts, verbose=args.verbose))

        print('\n' + '=' * 72)
        print('SKENARIO 3: Restricted Path (Forced Long Route)')
        print('=' * 72)
        results.append(run_restricted_path(net, hosts, verbose=args.verbose))

        csv_path = save_results(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        save_per_scenario_csvs(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        print('\nResults saved to:', csv_path)

    finally:
        restore_links(net)
        clear_switch_flows(net)
        kill_iperf_everywhere(net)
        try:
            net.stop()
        except Exception:
            pass
        stop_controller(ctrl_proc)


if __name__ == '__main__':
    setLogLevel('info')
    main()
