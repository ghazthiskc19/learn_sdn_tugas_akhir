#!/usr/bin/env python3
"""Simple experiment runner for the hierarchy topology.

This prototype builds a Mininet topology in-process (a hierarchy copy),
launches an OSKen controller, runs workloads and events, and collects metrics.

Supports:
- Single and concurrent flows (TCP/UDP)
- Bursty UDP workloads
- Controller log parsing for route convergence timing
- Link fail/recovery tests

It's intentionally small so you can extend scenarios in YAML under
`scripts/experiments/`.
"""
import argparse
import json
import os
import shlex
import signal
import subprocess
import threading
import time
from functools import partial

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink

from metrics import parse_ping, parse_iperf3, parse_traceroute, find_path_computed_timestamps


def build_hierarchy(net):
    """Create hosts, switches and links similar to topology-hierarchy.py

    Switch canonical names: s1..s15
    Hosts: Host1..Host12
    """
    # create switches
    s = {}
    for i in range(1, 16):
        s[i] = net.addSwitch(f"s{i}")

    # create hosts
    h = {}
    for i in range(1, 13):
        h[i] = net.addHost(f"Host{i}", ip=f"10.0.0.{i}/24")

    # map logical groups to switch numbers used in topology-hierarchy
    # core: s1..s3, dist: s4..s9, access: s10..s15
    core = (s[1], s[2], s[3])
    dist = (s[4], s[5], s[6], s[7], s[8], s[9])
    access = (s[10], s[11], s[12], s[13], s[14], s[15])

    # host links (Host1..Host4 -> Access s10,s11 ; Host5..Host8 -> s12,s13 ; Host9..Host12 -> s14,s15)
    net.addLink(h[1], access[0])
    net.addLink(h[2], access[0])
    net.addLink(h[3], access[1])
    net.addLink(h[4], access[1])

    net.addLink(h[5], access[2])
    net.addLink(h[6], access[2])
    net.addLink(h[7], access[3])
    net.addLink(h[8], access[3])

    net.addLink(h[9], access[4])
    net.addLink(h[10], access[4])
    net.addLink(h[11], access[5])
    net.addLink(h[12], access[5])

    # access <-> dist
    net.addLink(dist[0], access[0])
    net.addLink(dist[1], access[0])
    net.addLink(dist[0], access[1])
    net.addLink(dist[1], access[1])

    net.addLink(dist[2], access[2])
    net.addLink(dist[3], access[2])
    net.addLink(dist[2], access[3])
    net.addLink(dist[3], access[3])

    net.addLink(dist[4], access[4])
    net.addLink(dist[5], access[4])
    net.addLink(dist[4], access[5])
    net.addLink(dist[5], access[5])

    # dist <-> dist (pairwise)
    net.addLink(dist[0], dist[1])
    net.addLink(dist[2], dist[3])
    net.addLink(dist[4], dist[5])

    # dist -> core
    net.addLink(dist[0], core[0])
    net.addLink(dist[1], core[0])
    net.addLink(dist[2], core[1])
    net.addLink(dist[3], core[1])
    net.addLink(dist[4], core[2])
    net.addLink(dist[5], core[2])

    # core backbone
    net.addLink(core[0], core[1])
    net.addLink(core[1], core[2])
    net.addLink(core[0], core[2])

    return h, s


def run_ping(host, dst_ip, count=3, timeout=2):
    out = host.cmd(f"ping -c {count} -W {timeout} {dst_ip}")
    return parse_ping(out), out


def run_traceroute(host, dst_ip):
    out = host.cmd(f"traceroute -n -q 1 -w 1 {dst_ip}")
    return parse_traceroute(out), out


def run_iperf(host_src, host_dst, duration=5):
    # start server on dst
    host_dst.cmd("pkill -f iperf3 || true")
    server_cmd = f"iperf3 -s &"
    host_dst.cmd(server_cmd)
    time.sleep(0.5)
    out = host_src.cmd(f"iperf3 -c {host_dst.IP()} -t {duration} -f m")
    # stop server
    host_dst.cmd("pkill -f iperf3 || true")
    return parse_iperf3(out), out


def run_iperf_udp_burst(host_src, host_dst, bitrate="10M", burst_duration=1, burst_count=5, interval_between=1):
    """Run UDP bursts: send bitrate for burst_duration, wait interval_between, repeat burst_count times."""
    host_dst.cmd("pkill -f iperf3 || true")
    # start server on dst
    server_cmd = f"iperf3 -s -u &"
    host_dst.cmd(server_cmd)
    time.sleep(0.5)
    
    total_throughputs = []
    for burst_num in range(burst_count):
        out = host_src.cmd(f"iperf3 -c {host_dst.IP()} -u -b {bitrate} -t {burst_duration} -f m")
        tp = parse_iperf3(out)
        total_throughputs.append(tp)
        if burst_num < burst_count - 1:
            time.sleep(interval_between)
    
    host_dst.cmd("pkill -f iperf3 || true")
    avg_tp = sum(t for t in total_throughputs if t) / len([t for t in total_throughputs if t]) if total_throughputs else None
    return avg_tp, total_throughputs


def run_concurrent_flows(net, workloads, duration=10):
    """Run multiple concurrent iperf flows (specified as list of (src_host_name, dst_host_name, proto))."""
    threads = []
    results = {}
    
    def run_flow(src_name, dst_name, proto, idx):
        src = net.get(src_name)
        dst = net.get(dst_name)
        dst.cmd("pkill -f iperf3 || true")
        # start server
        cmd = "iperf3 -s"
        if proto == "udp":
            cmd += " -u"
        cmd += " &"
        dst.cmd(cmd)
        time.sleep(0.2)
        # run client
        client_cmd = f"iperf3 -c {dst.IP()} -t {duration} -f m"
        if proto == "udp":
            client_cmd += " -u -b 5M"
        out = src.cmd(client_cmd)
        results[idx] = (src_name, dst_name, proto, parse_iperf3(out))
        dst.cmd("pkill -f iperf3 || true")
    
    for idx, (src, dst, proto) in enumerate(workloads):
        t = threading.Thread(target=run_flow, args=(src, dst, proto, idx), daemon=True)
        t.start()
        threads.append(t)
    
    for t in threads:
        t.join(timeout=duration + 5)
    
    return results


def run_convergence_test(net, src_host, dst_host, link_pair, ctrl_log_path=None, down_delay=0.1, poll_interval=0.5, timeout=30):
    """Test route convergence after link failure.
    
    If ctrl_log_path is provided, parse controller logs for PATH-COMPUTED timestamps
    to measure when route was recomputed (more accurate than first-ping-reply).
    """
    # ensure baseline: at least one successful ping
    dst_ip = dst_host.IP()
    ok = False
    for _ in range(5):
        res, _ = run_ping(src_host, dst_ip, count=1)
        if res and res[1] == 1:
            ok = True
            break
        time.sleep(0.2)
    if not ok:
        print("Baseline connectivity failed; convergence test aborted")
        return None

    # bring link down
    sw1, sw2 = link_pair
    t0 = time.time()
    net.configLinkStatus(sw1.name, sw2.name, 'down')
    print(f"[t={0:.2f}] Link {sw1.name}--{sw2.name} DOWN")
    
    # poll for recovery (ICMP-based)
    icmp_recovered_at = None
    end = t0 + timeout
    while time.time() < end:
        res, _ = run_ping(src_host, dst_ip, count=1)
        if res and res[1] == 1:
            icmp_recovered_at = time.time()
            print(f"[t={icmp_recovered_at - t0:.2f}] ICMP recovered")
            break
        time.sleep(poll_interval)
    
    # restore link
    net.configLinkStatus(sw1.name, sw2.name, 'up')
    print(f"[t={time.time() - t0:.2f}] Link restored")
    
    results = {}
    if icmp_recovered_at:
        results['icmp_convergence_s'] = icmp_recovered_at - t0
    else:
        results['icmp_convergence_s'] = None
    
    # if controller log available, parse PATH-COMPUTED to find when route was recomputed
    if ctrl_log_path:
        # extract src/dst DPID from host names (assuming Host1..Host12 map to known switches)
        # This is a simplified mapping; extend as needed for your topology
        host_to_dpid = {f'Host{i}': i+9 for i in range(1, 13)}  # Host1->10, ..., Host12->21
        src_dpid = host_to_dpid.get(src_host.name)
        dst_dpid = host_to_dpid.get(dst_host.name)
        if src_dpid and dst_dpid:
            paths = find_path_computed_timestamps(ctrl_log_path, src_dpid, dst_dpid)
            if paths:
                results['ctrl_path_computed'] = paths
    
    return results


def load_config(path):
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception:
        # fallback to JSON
        with open(path) as f:
            return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', help='experiment config (yaml or json)')
    parser.add_argument('--no-plots', action='store_true', help='Skip post-processing plots')
    args = parser.parse_args()

    cfg = load_config(args.config)
    out_dir = cfg.get('output', 'results')
    os.makedirs(out_dir, exist_ok=True)

    # start controller (and redirect logs)
    ctrl_cmd = cfg.get('controller', {}).get('cmd', 'python3 SPF/dijkstra_osken_controller.py')
    ctrl_log_path = os.path.join(out_dir, 'controller.log')
    print('Starting controller:', ctrl_cmd)
    with open(ctrl_log_path, 'w') as ctrl_log:
        ctrl_proc = subprocess.Popen(shlex.split(ctrl_cmd), stdout=ctrl_log, stderr=subprocess.STDOUT)
    time.sleep(1.5)

    net = Mininet(controller=partial(RemoteController, ip='127.0.0.1', port=6633), link=TCLink,
                  autoSetMacs=True, autoStaticArp=True, waitConnected=True)

    # build topology in-process based on config
    topology_type = cfg.get('topology', 'hierarchy')
    print(f"Building topology: {topology_type}")
    
    if topology_type == 'mesh':
        h, s = build_mesh(net)
    else:
        h, s = build_hierarchy(net)
    
    net.start()
    time.sleep(1)

    results = []

    trials = cfg.get('trials', 1)
    for trial in range(1, trials + 1):
        print(f'\n=== Trial {trial}/{trials} ===')
        
        for workload in cfg.get('workloads', []):
            src_name = workload['src']
            dst_name = workload['dst']
            src_host = net.get(src_name)
            dst_host = net.get(dst_name)
            # start-after
            sd = workload.get('start_delay', 0)
            if sd > 0:
                time.sleep(sd)
            
            wl_type = workload.get('type', 'throughput')
            
            if wl_type == 'throughput':
                proto = workload.get('proto', 'tcp')
                duration = workload.get('duration', 5)
                tp, raw = run_iperf(src_host, dst_host, duration=duration)
                print(f"  {workload['name']} (TCP): {tp} Mbps")
                results.append({'trial': trial, 'workload': workload['name'], 'type': 'throughput_mbps', 'value': tp})
            
            elif wl_type == 'udp_burst':
                bitrate = workload.get('bitrate', '10M')
                burst_duration = workload.get('burst_duration', 1)
                burst_count = workload.get('burst_count', 3)
                interval = workload.get('interval_between', 1)
                avg_tp, bursts = run_iperf_udp_burst(src_host, dst_host, bitrate=bitrate, 
                                                      burst_duration=burst_duration, 
                                                      burst_count=burst_count, 
                                                      interval_between=interval)
                print(f"  {workload['name']} (UDP Burst): avg {avg_tp} Mbps, bursts {bursts}")
                results.append({'trial': trial, 'workload': workload['name'], 'type': 'udp_burst_avg_mbps', 'value': avg_tp})
                results.append({'trial': trial, 'workload': workload['name'], 'type': 'udp_burst_details', 'value': bursts})
            
            # latency
            ping_res, ping_raw = run_ping(src_host, dst_host.IP(), count=3)
            print(f"  {workload['name']}: latency {ping_res[3] if ping_res[3] else 'N/A'} ms, loss {ping_res[2]}%")
            results.append({'trial': trial, 'workload': workload['name'], 'type': 'latency_ms', 'value': ping_res[3]})
            results.append({'trial': trial, 'workload': workload['name'], 'type': 'loss_percent', 'value': ping_res[2]})
            
            # traceroute
            hops, tr_raw = run_traceroute(src_host, dst_host.IP())
            print(f"  {workload['name']}: {hops} hops")
            results.append({'trial': trial, 'workload': workload['name'], 'type': 'hop_count', 'value': hops})

        # concurrent flows (if specified)
        concurrent = cfg.get('concurrent_flows', [])
        if concurrent:
            print(f"  Running {len(concurrent)} concurrent flows...")
            flow_results = run_concurrent_flows(net, concurrent, duration=cfg.get('concurrent_duration', 10))
            for idx, (src, dst, proto, tp) in flow_results.items():
                print(f"    Flow {idx} ({proto}): {tp} Mbps")
                results.append({'trial': trial, 'concurrent_flow': idx, 'src': src, 'dst': dst, 'proto': proto, 'throughput_mbps': tp})

        # events (link failures, etc.)
        for ev in cfg.get('events', []):
            if ev.get('action') == 'link-down':
                sw1 = net.get(ev['src_switch'])
                sw2 = net.get(ev['dst_switch'])
                at = ev.get('at', 0)
                duration = ev.get('duration', 2)
                time.sleep(max(0, at - time.time()))  # wait until event time
                print(f"  Event: bringing link {sw1.name} <-> {sw2.name} down for convergence test")
                conv = run_convergence_test(net, net.get('Host1'), net.get('Host12'), (sw1, sw2), 
                                           ctrl_log_path=ctrl_log_path, timeout=30)
                print(f"    Convergence: {conv}")
                results.append({'trial': trial, 'event': ev.get('name'), 'convergence': conv})

    # teardown
    net.stop()
    ctrl_proc.terminate()
    try:
        ctrl_proc.wait(timeout=2)
    except Exception:
        ctrl_proc.kill()

    out_file = os.path.join(out_dir, 'results.json')
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f'\nResults written to {out_file}')
    print(f'Controller log: {ctrl_log_path}')
    
    # Post-process: generate CSV and plots
    if not args.no_plots:
        print('\nPost-processing results...')
        try:
            from postprocess_results import load_results, flatten_results, write_csv, aggregate_by_metric
            from postprocess_results import plot_metrics, plot_throughput_comparison, plot_latency_distribution
            from postprocess_results import plot_convergence_times, generate_summary_stats
            
            results_data = load_results(out_file)
            
            # CSV
            rows = flatten_results(results_data)
            csv_path = os.path.join(out_dir, 'results.csv')
            write_csv(rows, csv_path)
            
            # Plots
            metrics = aggregate_by_metric(results_data)
            plot_metrics(metrics, out_dir)
            plot_throughput_comparison(results_data, out_dir)
            plot_latency_distribution(results_data, out_dir)
            plot_convergence_times(results_data, out_dir)
            
            # Summary
            generate_summary_stats(results_data, out_dir)
            print('Post-processing complete!')
        except Exception as e:
            print(f'Post-processing failed: {e}')
            print('Run manually: python3 scripts/experiment_system/postprocess_results.py {out_file}')


if __name__ == '__main__':
    main()
