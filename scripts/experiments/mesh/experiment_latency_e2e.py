#!/usr/bin/env python3
"""
Mesh-specific end-to-end latency experiment.

Scenarios:
1. UDP jitter and packet loss
2. First packet vs subsequent packet latency
3. Latency under congestion
4. Latency during convergence (direct link failure)
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


def kill_iperf_everywhere(net):
    for host in net.hosts:
        try:
            host.cmd('killall -9 iperf 2>/dev/null || true')
        except Exception:
            pass


def extract_first_time_ms(output):
    for line in output.splitlines():
        if 'time=' in line:
            match = re.search(r'time=([0-9]+(?:\.[0-9]+)?)\s*ms', line)
            if match:
                return float(match.group(1))
    return None


def extract_all_times_ms(output):
    values = []
    for line in output.splitlines():
        match = re.search(r'time=([0-9]+(?:\.[0-9]+)?)\s*ms', line)
        if match:
            values.append(float(match.group(1)))
    return values


def extract_rtt_summary(output):
    match = re.search(
        r'rtt [^=]+=[\s]*([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)',
        output,
    )
    if not match:
        return None
    return {
        'min': float(match.group(1)),
        'avg': float(match.group(2)),
        'max': float(match.group(3)),
        'mdev': float(match.group(4)),
    }


def extract_udp_metrics(output):
    jitter_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*ms\s*jitter', output, flags=re.IGNORECASE)
    loss_match = re.search(r'(\d+(?:\.\d+)?)%\s*packet loss', output, flags=re.IGNORECASE)
    if not loss_match:
        loss_match = re.search(r'\d+/\d+\s*\((\d+(?:\.\d+)?)%\)', output)
    return {
        'jitter_ms': float(jitter_match.group(1)) if jitter_match else None,
        'packet_loss_pct': float(loss_match.group(1)) if loss_match else None,
    }


def measure_udp_jitter_loss(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    kill_iperf_everywhere(net)
    host_e1.cmd('iperf -s -u -p 5001 &')
    time.sleep(0.5)
    output = host_a1.cmd('iperf -c 10.0.0.7 -u -b 10M -t 10 -p 5001')
    if verbose:
        print(output)
    metrics = extract_udp_metrics(output)
    kill_iperf_everywhere(net)
    return metrics


def measure_first_vs_subsequent(host_a1, host_e1_ip, verbose=False):
    output = host_a1.cmd(f'ping -c 5 {host_e1_ip}')
    if verbose:
        print(output)
    times = extract_all_times_ms(output)
    first = times[0] if times else None
    subsequent = sum(times[1:]) / len(times[1:]) if len(times) > 1 else None
    return {
        'first_packet_latency_ms': first,
        'subsequent_packet_latency_ms': subsequent,
    }


def measure_congestion_latency(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_b1 = hosts['HostB1']
    host_a2 = hosts['HostA2']
    host_d1 = hosts['HostD1']
    host_e2 = hosts['HostE2']
    kill_iperf_everywhere(net)
    host_d1.cmd('iperf -s -p 5001 &')
    host_e2.cmd('iperf -s -p 5002 &')
    time.sleep(0.5)
    host_b1.cmd('iperf -c 10.0.0.5 -t 20 -p 5001 &')
    host_a2.cmd('iperf -c 10.0.0.8 -t 20 -p 5002 &')
    time.sleep(1)
    output = host_a1.cmd('ping -c 15 10.0.0.7')
    if verbose:
        print(output)
    summary = extract_rtt_summary(output)
    kill_iperf_everywhere(net)
    return {'latency_under_congestion_ms': summary['avg'] if summary else None}


def measure_failover_latency(net, hosts, verbose=False):
    host_a1 = hosts['HostA1']
    host_e1 = hosts['HostE1']
    kill_iperf_everywhere(net)
    p = host_a1.popen('ping -c 30 -i 0.2 10.0.0.7', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)
    net.configLinkStatus('SwitchA', 'SwitchE', 'down')
    out_bytes, _ = p.communicate()
    output = out_bytes.decode('utf-8', errors='ignore') if isinstance(out_bytes, (bytes, bytearray)) else str(out_bytes)
    if verbose:
        print(output)
    loss_match = re.search(r'(\d+(?:\.\d+)?)% packet loss', output)
    summary = extract_rtt_summary(output)
    spike = summary['max'] if summary else None
    net.configLinkStatus('SwitchA', 'SwitchE', 'up')
    kill_iperf_everywhere(net)
    return {
        'packet_loss_pct': float(loss_match.group(1)) if loss_match else None,
        'latency_spike_ms': spike,
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


def save_results(rows, output_dir='results/mesh/latency', algo_name='unknown', metric_name='latency'):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))
    fieldnames = sorted({key for row in rows for key in row.keys()})
    ordered = ['scenario'] + [k for k in fieldnames if k != 'scenario']
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ordered)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return csv_path


def save_per_scenario_csvs(rows, output_dir='results/mesh/latency', algo_name='unknown', metric_name='latency'):
    os.makedirs(output_dir, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    ordered = ['scenario'] + [k for k in fieldnames if k != 'scenario']
    paths = []
    for idx, row in enumerate(rows, 1):
        path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, idx))
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=ordered)
            writer.writeheader()
            writer.writerow(row)
        paths.append(path)
    return paths


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
    parser = argparse.ArgumentParser(description='End-to-End Latency Experiment (Mesh Topology)')
    parser.add_argument('--controller-cmd', help='Controller command to start', default=None)
    parser.add_argument('--algo-name', help='Algorithm label for CSV filenames (e.g., dijkstra, astar)', default=None)
    parser.add_argument('--output-dir', help='Output directory for results', default='results/mesh/latency')
    parser.add_argument('--no-controller', help='Do not auto-start controller', action='store_true')
    parser.add_argument('--verbose', help='Verbose logging', action='store_true')
    args = parser.parse_args(argv)
    metric_name = 'latency'
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
        host_a1 = hosts['HostA1']
        host_e1_ip = '10.0.0.7'
        results = []

        print('\n' + '=' * 72)
        print('SKENARIO 1: UDP Latency on Mesh')
        print('=' * 72)
        results.append({'scenario': 'UDP Latency', **measure_udp_jitter_loss(net, hosts, verbose=args.verbose)})

        print('\n' + '=' * 72)
        print('SKENARIO 2: First Packet vs Subsequent Packet Latency')
        print('=' * 72)
        clear_switch_flows(net)
        time.sleep(1)
        results.append({'scenario': 'First vs Subsequent', **measure_first_vs_subsequent(host_a1, host_e1_ip, verbose=args.verbose)})

        print('\n' + '=' * 72)
        print('SKENARIO 3: Latency Under Congestion')
        print('=' * 72)
        clear_switch_flows(net)
        time.sleep(1)
        results.append({'scenario': 'Congestion', **measure_congestion_latency(net, hosts, verbose=args.verbose)})

        print('\n' + '=' * 72)
        print('SKENARIO 4: Latency During Convergence')
        print('=' * 72)
        clear_switch_flows(net)
        time.sleep(1)
        results.append({'scenario': 'Failover', **measure_failover_latency(net, hosts, verbose=args.verbose)})

        csv_path = save_results(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        save_per_scenario_csvs(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        print('\nResults saved to:', csv_path)

    finally:
        restore_links(net)
        kill_iperf_everywhere(net)
        try:
            net.stop()
        except Exception:
            pass
        stop_controller(ctrl_proc)


if __name__ == '__main__':
    setLogLevel('info')
    main()
