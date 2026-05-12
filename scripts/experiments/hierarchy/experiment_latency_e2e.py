#!/usr/bin/env python3
"""
Experiment 2: End-to-End Latency Measurement (Hierarchy Topology)

Four scenarios implemented as functions:
 - scenario_udp_jitter_loss(net, hosts)
 - scenario_first_vs_subsequent_ping(net, hosts)
 - scenario_latency_under_congestion(net, hosts)
 - scenario_latency_during_convergence(net, hosts)

Script uses Mininet API and regex parsing for metric extraction.
"""

import os
import sys
import re
import time
import csv
import argparse
import subprocess

from mininet.net import Mininet
from mininet.node import RemoteController

# Allow importing sibling script for topology if present
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Try to import HierarchyTopo from experiment_convergence_route.py if available
HierarchyTopo = None
try:
    import experiment_convergence_route as ecr
    HierarchyTopo = getattr(ecr, 'HierarchyTopo', None)
except Exception:
    HierarchyTopo = None


def start_controller(cmd):
    if not cmd:
        return None
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # give controller time to initialize
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
    """Build Mininet network using HierarchyTopo if available."""
    if HierarchyTopo:
        topo = HierarchyTopo()
        net = Mininet(topo=topo, controller=None, autoSetMacs=True, autoStaticArp=True)
    else:
        # Fallback: try to use an existing topology script in SPF as simple demo
        from mininet.topo import LinearTopo
        topo = LinearTopo(k=3)
        net = Mininet(topo=topo, controller=None, autoSetMacs=True, autoStaticArp=True)
    return net


def find_hosts(net):
    """Return commonly used host objects by name if they exist in net."""
    # Names used in hierarchy: h1..h12
    hosts = {}
    for i in range(1, 13):
        name = 'h%d' % i
        try:
            hosts[name] = net.get(name)
        except Exception:
            hosts[name] = None
    return hosts


def _regex_search(patterns, text):
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m
    return None


def scenario_udp_jitter_loss(net, hosts, verbose=False):
    """Skenario 1: UDP traffic (iperf) - extract jitter (ms) and packet loss (%)"""
    h1 = hosts.get('h1')
    h12 = hosts.get('h12')
    result = {'scenario': 'udp_jitter_loss', 'jitter_ms': None, 'packet_loss_pct': None}
    if not h1 or not h12:
        result['error'] = 'hosts_missing'
        return result

    # Start UDP server on Host12
    h12.cmd('killall -9 iperf 2>/dev/null || true')
    server_cmd = 'iperf -s -u -p 5001 &'
    if verbose: print('Starting UDP server on h12')
    h12.cmd(server_cmd)
    time.sleep(0.5)

    # Run client on Host1: 10Mbps for 10s
    client_cmd = 'iperf -c 10.0.0.12 -u -b 10M -t 10 -p 5001'
    if verbose: print('Running UDP client on h1...')
    out = h1.cmd(client_cmd)
    if verbose:
        print('iperf client output:\n', out)

    # iperf UDP client output usually contains "Jitter" and "loss" on the server and client.
    # Try several regex patterns to extract jitter and packet loss.
    # Example iperf client UDP summary:
    # [  3]  0.0-10.0 sec  12.3 MBytes  10.3 Mbits/sec  0.052 ms jitter 0/10000 (0%)

    jitter_pat = r"([0-9]+(?:\.[0-9]+)?)\s*ms\s*jitter"
    loss_pat = r"\((\d+(?:\.\d+)?)%\)"  # matches (0%) or (12.3%) occurrences

    m_j = re.search(jitter_pat, out, flags=re.IGNORECASE)
    if m_j:
        result['jitter_ms'] = float(m_j.group(1))

    # For packet loss, search for patterns like '(0%)' after a fraction '0/10000 (0%)'
    m_loss = re.search(r"\d+/\d+\s*\((\d+(?:\.\d+)?)%\)", out)
    if not m_loss:
        # fallback: any (xx%) occurrence
        m_loss = re.search(loss_pat, out)
    if m_loss:
        result['packet_loss_pct'] = float(m_loss.group(1))

    # Cleanup
    h1.cmd('killall -9 iperf 2>/dev/null || true')
    h12.cmd('killall -9 iperf 2>/dev/null || true')
    time.sleep(0.2)
    return result


def scenario_first_vs_subsequent_ping(net, hosts, verbose=False):
    """Skenario 2: First packet latency vs subsequent packet latency (ping)"""
    h1 = hosts.get('h1')
    h9 = hosts.get('h9')
    result = {'scenario': 'first_vs_subsequent', 'first_packet_ms': None, 'subsequent_avg_ms': None}
    if not h1 or not h9:
        result['error'] = 'hosts_missing'
        return result

    # Ensure no prior ping flows: we simply run the ping and trust the first packet triggers Packet-In
    out = h1.cmd('ping -c 5 10.0.0.9')
    if verbose:
        print('ping output:\n', out)

    # Parse lines for time=... ms
    times = []
    for line in out.splitlines():
        m = re.search(r'time=([0-9]+(?:\.[0-9]+)?)\s*ms', line)
        if m:
            times.append(float(m.group(1)))

    if len(times) >= 1:
        result['first_packet_ms'] = times[0]
    if len(times) >= 2:
        subsequent = times[1:]
        result['subsequent_avg_ms'] = sum(subsequent) / len(subsequent)
    return result


def scenario_latency_under_congestion(net, hosts, verbose=False):
    """Skenario 3: Start background TCP iperf flows to create congestion, then ping target and parse rtt avg"""
    h1 = hosts.get('h1')
    h2 = hosts.get('h2')
    h3 = hosts.get('h3')
    h4 = hosts.get('h4')
    h5 = hosts.get('h5')
    h6 = hosts.get('h6')
    h10 = hosts.get('h10')
    h12 = hosts.get('h12')

    result = {'scenario': 'congestion', 'rtt_avg_ms': None}
    # Verify required hosts
    if not (h1 and h2 and h3 and h4 and h5 and h6 and h10 and h12):
        result['error'] = 'hosts_missing'
        return result

    # Start iperf servers
    h5.cmd('killall -9 iperf 2>/dev/null || true')
    h6.cmd('killall -9 iperf 2>/dev/null || true')
    h10.cmd('killall -9 iperf 2>/dev/null || true')
    h5.cmd('iperf -s -p 5001 &')
    h6.cmd('iperf -s -p 5002 &')
    h10.cmd('iperf -s -p 5003 &')
    time.sleep(0.5)

    # Start clients that generate background traffic for 20s
    h2.cmd('iperf -c 10.0.0.5 -t 20 -p 5001 &')
    h3.cmd('iperf -c 10.0.0.6 -t 20 -p 5002 &')
    h4.cmd('iperf -c 10.0.0.10 -t 20 -p 5003 &')
    time.sleep(1.0)  # let flows ramp up

    # Measure latency from h1 to h12 (15 pings)
    out = h1.cmd('ping -c 15 10.0.0.12')
    if verbose:
        print('ping under congestion output:\n', out)

    # Extract rtt line: rtt min/avg/max/mdev = a/b/c/d ms
    m = re.search(r'rtt [^=]+=\s*([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)', out)
    if m:
        avg = float(m.group(2))
        result['rtt_avg_ms'] = avg

    # cleanup
    for h in (h2, h3, h4, h5, h6, h10):
        try:
            h.cmd('killall -9 iperf 2>/dev/null || true')
        except Exception:
            pass
    time.sleep(0.2)
    return result


def scenario_latency_during_convergence(net, hosts, verbose=False):
    """Skenario 4: Start long ping via popen, trigger link down, then parse packet loss and max rtt"""
    h1 = hosts.get('h1')
    h12 = hosts.get('h12')
    result = {'scenario': 'convergence_latency_spike', 'packet_loss_pct': None, 'rtt_max_ms': None}
    if not h1 or not h12:
        result['error'] = 'hosts_missing'
        return result

    # Ensure iperf not interfering
    h1.cmd('killall -9 iperf 2>/dev/null || true')
    h12.cmd('killall -9 iperf 2>/dev/null || true')

    # Start long ping via popen
    p = h1.popen('ping -c 30 -i 0.2 10.0.0.12', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(2)  # let ping stabilize

    # Trigger link failure: Core1-Core3 down
    try:
        net.configLinkStatus('Core1', 'Core3', 'down')
    except Exception:
        # If topology uses different switch names, try numeric names
        try:
            net.configLinkStatus('s1', 's3', 'down')
        except Exception:
            pass

    out_bytes, _ = p.communicate()
    try:
        out = out_bytes.decode('utf-8', errors='ignore')
    except Exception:
        out = str(out_bytes)

    if verbose:
        print('ping during convergence output:\n', out)

    # Extract packet loss: "X% packet loss"
    m_loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", out)
    if m_loss:
        result['packet_loss_pct'] = float(m_loss.group(1))

    # Extract rtt max from rtt line
    m_rtt = re.search(r'rtt [^=]+=\s*([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)/([0-9]+(?:\.[0-9]+)?)', out)
    if m_rtt:
        # group 3 is max
        result['rtt_max_ms'] = float(m_rtt.group(3))

    # Restore link
    try:
        net.configLinkStatus('Core1', 'Core3', 'up')
    except Exception:
        try:
            net.configLinkStatus('s1', 's3', 'up')
        except Exception:
            pass

    # Ensure iperf processes terminated
    h1.cmd('killall -9 iperf 2>/dev/null || true')
    h12.cmd('killall -9 iperf 2>/dev/null || true')
    time.sleep(0.2)
    return result


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


def save_results(results, output_dir='results/hierarchy/latency', algo_name='unknown', metric_name='latency'):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))
    # Collect all keys
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ['scenario'] + sorted(k for k in keys if k != 'scenario')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    return csv_path


def save_per_scenario_csvs(results, output_dir='results/hierarchy/latency', algo_name='unknown', metric_name='latency'):
    os.makedirs(output_dir, exist_ok=True)
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ['scenario'] + sorted(k for k in keys if k != 'scenario')

    paths = []
    for idx, row in enumerate(results, 1):
        path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, idx))
        with open(path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerow(row)
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description='End-to-End Latency Measurement Experiment (Hierarchy)')
    parser.add_argument('--controller-cmd', help='Controller command to start', default=None)
    parser.add_argument('--algo-name', help='Algorithm label for CSV filenames (e.g., dijkstra, astar)', default=None)
    parser.add_argument('--output-dir', help='Output directory for results', default='results/hierarchy/latency')
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
        net.start()
        hosts = find_hosts(net)
        if args.verbose:
            print('Hosts discovered:', [k for k, v in hosts.items() if v])

        results = []
        # Run scenarios
        r1 = scenario_udp_jitter_loss(net, hosts, verbose=args.verbose)
        results.append(r1)
        time.sleep(1)

        r2 = scenario_first_vs_subsequent_ping(net, hosts, verbose=args.verbose)
        results.append(r2)
        time.sleep(1)

        r3 = scenario_latency_under_congestion(net, hosts, verbose=args.verbose)
        results.append(r3)
        time.sleep(1)

        r4 = scenario_latency_during_convergence(net, hosts, verbose=args.verbose)
        results.append(r4)

        csv_path = save_results(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        save_per_scenario_csvs(results, output_dir=args.output_dir, algo_name=algo_name, metric_name=metric_name)
        print('\nResults saved to:', csv_path)

    finally:
        try:
            net.stop()
        except Exception:
            pass
        stop_controller(ctrl_proc)


if __name__ == '__main__':
    main()
