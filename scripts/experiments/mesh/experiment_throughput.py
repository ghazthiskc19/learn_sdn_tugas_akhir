#!/usr/bin/env python3
"""
Mesh-specific throughput experiment using iperf3.

Scenarios:
1. Baseline throughput
2. Multi-flow stress test via cross-traffic
3. Throughput during failover
4. Throughput by TCP MSS size
"""

import argparse
import csv
import os
import re
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


def kill_iperf3_on_hosts(hosts):
    for host in hosts.values():
        try:
            host.cmd('killall -9 iperf3 2>/dev/null || true')
        except Exception:
            pass


def parse_iperf3_sender(output):
    if isinstance(output, (bytes, bytearray)):
        output = output.decode('utf-8', errors='ignore')
    sender_line = ''
    for line in output.splitlines():
        if 'sender' in line.lower():
            sender_line = line.strip()
    if not sender_line:
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        sender_line = lines[-1] if lines else ''

    transfer = None
    bitrate = None
    retransmits = None

    m = re.search(
        r'([0-9]+(?:\.[0-9]+)?\s*(?:KBytes|MBytes|GBytes))\s+'
        r'([0-9]+(?:\.[0-9]+)?\s*(?:Kbits/sec|Mbits/sec|Gbits/sec))\s+'
        r'(\d+)\s+.*sender',
        sender_line,
        flags=re.IGNORECASE,
    )
    if m:
        transfer = m.group(1)
        bitrate = m.group(2)
        retransmits = int(m.group(3))
    else:
        m_tr = re.search(r'([0-9]+(?:\.[0-9]+)?\s*(?:KBytes|MBytes|GBytes))', sender_line, flags=re.IGNORECASE)
        m_br = re.search(r'([0-9]+(?:\.[0-9]+)?\s*(?:Kbits/sec|Mbits/sec|Gbits/sec))', sender_line, flags=re.IGNORECASE)
        m_re = re.search(r'\s(\d+)\s+sender', sender_line, flags=re.IGNORECASE)
        if m_tr:
            transfer = m_tr.group(1)
        if m_br:
            bitrate = m_br.group(1)
        if m_re:
            retransmits = int(m_re.group(1))

    return {
        'transfer': transfer,
        'bitrate': bitrate,
        'retransmits': retransmits,
    }


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


def save_results(rows, output_dir='results/mesh/throughput', algo_name='unknown', metric_name='throughput'):
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


def save_per_scenario_csvs(rows, output_dir='results/mesh/throughput', algo_name='unknown', metric_name='throughput'):
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


def measure_baseline(hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    kill_iperf3_on_hosts(hosts)
    host_e1.cmd('iperf3 -s -D')
    time.sleep(0.5)
    output = host_a1.cmd('iperf3 -c 10.0.0.7 -t 10')
    if verbose:
        print(output)
    return parse_iperf3_sender(output)


def measure_multiflow(hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_b1 = hosts['HostB1']
    host_a2 = hosts['HostA2']
    host_b = hosts['HostB1']
    host_d1 = hosts['HostD1']
    host_e1 = hosts['HostE1']
    host_e2 = hosts['HostE2']
    kill_iperf3_on_hosts(hosts)
    host_e1.cmd('iperf3 -s -p 5201 -D')
    host_d1.cmd('iperf3 -s -p 5202 -D')
    host_e2.cmd('iperf3 -s -p 5203 -D')
    time.sleep(0.5)

    p1 = host_a1.popen('iperf3 -c 10.0.0.7 -p 5201 -t 15', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p2 = host_b1.popen('iperf3 -c 10.0.0.5 -p 5202 -t 15', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p3 = host_a2.popen('iperf3 -c 10.0.0.8 -p 5203 -t 15', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out1, _ = p1.communicate()
    p2.communicate()
    p3.communicate()
    output = out1.decode('utf-8', errors='ignore') if isinstance(out1, (bytes, bytearray)) else str(out1)
    if verbose:
        print(output)
    return parse_iperf3_sender(output)


def measure_failover(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    kill_iperf3_on_hosts(hosts)
    host_e1.cmd('iperf3 -s -p 5204 -D')
    time.sleep(0.5)
    p = host_a1.popen('iperf3 -c 10.0.0.7 -p 5204 -t 20', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5)
    net.configLinkStatus('SwitchA', 'SwitchE', 'down')
    out_bytes, _ = p.communicate()
    output = out_bytes.decode('utf-8', errors='ignore') if isinstance(out_bytes, (bytes, bytearray)) else str(out_bytes)
    if verbose:
        print(output)
    result = parse_iperf3_sender(output)
    try:
        net.configLinkStatus('SwitchA', 'SwitchE', 'up')
    except Exception:
        pass
    return result


def measure_mss_compare(hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    kill_iperf3_on_hosts(hosts)
    host_e1.cmd('iperf3 -s -D')
    time.sleep(0.5)

    out_small = host_a1.cmd('iperf3 -c 10.0.0.7 -M 500 -t 10')
    out_large = host_a1.cmd('iperf3 -c 10.0.0.7 -M 1460 -t 10')
    if verbose:
        print(out_small)
        print(out_large)

    parsed_small = parse_iperf3_sender(out_small)
    parsed_large = parse_iperf3_sender(out_large)
    return {
        'small_transfer': parsed_small['transfer'],
        'small_bitrate': parsed_small['bitrate'],
        'small_retransmits': parsed_small['retransmits'],
        'large_transfer': parsed_large['transfer'],
        'large_bitrate': parsed_large['bitrate'],
        'large_retransmits': parsed_large['retransmits'],
    }


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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Throughput Measurement Experiment (Mesh Topology)')
    parser.add_argument('--controller-cmd', help='Controller command to start', default=None)
    parser.add_argument('--algo-name', help='Algorithm label for CSV filenames (e.g., dijkstra, astar)', default=None)
    parser.add_argument('--output-dir', help='Output directory for results', default='results/mesh/throughput')
    parser.add_argument('--no-controller', help='Do not auto-start controller', action='store_true')
    parser.add_argument('--verbose', help='Verbose logging', action='store_true')
    args = parser.parse_args(argv)
    metric_name = 'throughput'
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
        print('SKENARIO 1: Throughput Maksimum (Baseline)')
        print('=' * 72)
        results.append({'scenario': 'Throughput Baseline', **measure_baseline(hosts, verbose=args.verbose)})
        kill_iperf3_on_hosts(hosts)
        time.sleep(1)

        print('\n' + '=' * 72)
        print('SKENARIO 2: Throughput Multi-Flow (Stress Test via Cross-Traffic)')
        print('=' * 72)
        results.append({'scenario': 'Multi-Flow Stress', **measure_multiflow(hosts, verbose=args.verbose)})
        kill_iperf3_on_hosts(hosts)
        time.sleep(1)

        print('\n' + '=' * 72)
        print('SKENARIO 3: Throughput Saat Terjadi Failover')
        print('=' * 72)
        results.append({'scenario': 'Failover', **measure_failover(net, hosts, verbose=args.verbose)})
        kill_iperf3_on_hosts(hosts)
        time.sleep(1)

        print('\n' + '=' * 72)
        print('SKENARIO 4: Throughput Berdasarkan Ukuran Paket (TCP MSS)')
        print('=' * 72)
        results.append({'scenario': 'MSS Compare', **measure_mss_compare(hosts, verbose=args.verbose)})
        kill_iperf3_on_hosts(hosts)

        csv_path = save_results(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        save_per_scenario_csvs(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        print('\nResults saved to:', csv_path)

    finally:
        restore_links(net)
        kill_iperf3_on_hosts({host.name: host for host in net.hosts})
        try:
            net.stop()
        except Exception:
            pass
        stop_controller(ctrl_proc)


if __name__ == '__main__':
    setLogLevel('info')
    main()
