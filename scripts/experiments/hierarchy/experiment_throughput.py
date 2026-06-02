#!/usr/bin/env python3
"""
Experiment 3: Throughput Measurement using iperf3 (Hierarchy Topology)

Four scenarios implemented as functions:
 - scenario_throughput_baseline(net, hosts)
 - scenario_throughput_multiflow(net, hosts)
 - scenario_throughput_failover(net, hosts)
 - scenario_throughput_mss_compare(net, hosts)

Outputs saved to CSV in results/throughput/
"""

import argparse
import csv
import os
import re
import resource
import subprocess
import sys
import time
from typing import Dict, Optional

from mininet.net import Mininet

# allow local imports
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

HierarchyTopo = None
try:
    import experiment_convergence_route as ecr

    HierarchyTopo = getattr(ecr, "HierarchyTopo", None)
except Exception:
    HierarchyTopo = None


def patch_resource_limits():
    """Silently attempt to raise resource limits; ignore if not permitted."""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    except Exception:
        pass


def cleanup_mininet():
    """Run 'mn -c' to remove leftover interfaces and OVS bridges."""
    try:
        subprocess.run(
            ["mn", "-c"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception:
        pass


def start_controller(cmd):
    if not cmd:
        return None
    proc = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
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
    if HierarchyTopo:
        topo = HierarchyTopo()
        net = Mininet(topo=topo, controller=None, autoSetMacs=True, autoStaticArp=True)
    else:
        from mininet.topo import LinearTopo

        topo = LinearTopo(k=3)
        net = Mininet(topo=topo, controller=None, autoSetMacs=True, autoStaticArp=True)
    return net


def find_hosts(net):
    hosts = {}
    for i in range(1, 13):
        canonical = "Host%d" % i
        alias = "h%d" % i
        node = None
        try:
            node = net.get(canonical)
        except Exception:
            pass
        if node is None:
            try:
                node = net.get(alias)
            except Exception:
                pass
        hosts[alias] = node  # always keyed as h1..h12
    return hosts


def parse_iperf3_sender(output) -> Dict[str, Optional[object]]:
    """Parse iperf3 output and return dict with transfer, bitrate, retr.
    Works by finding the sender summary line containing 'sender'."""
    if isinstance(output, bytes):
        try:
            output = output.decode("utf-8", errors="ignore")
        except Exception:
            output = str(output)
    sender_line = None
    for line in output.splitlines():
        if "sender" in line.lower():
            sender_line = line.strip()
    if not sender_line:
        # fallback: try last non-empty line
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        sender_line = lines[-1] if lines else ""

    res: Dict[str, Optional[object]] = {
        "transfer": None,
        "bitrate": None,
        "retransmits": None,
    }
    # Try structured regex: transfer (MBytes/GBytes)  bitrate (Mbits/sec/Gbits/sec)  retrans
    m = re.search(
        r"([0-9]+(?:\.[0-9]+)?\s*(?:MBytes|GBytes))\s+([0-9]+(?:\.[0-9]+)?\s*(?:Mbits/sec|Gbits/sec))\s+(\d+)\s+.*sender",
        sender_line,
        flags=re.IGNORECASE,
    )
    if not m:
        # Some iperf3 variants print without retrans column; try capturing transfer and bitrate
        m = re.search(
            r"([0-9]+(?:\.[0-9]+)?\s*(?:MBytes|GBytes))\s+([0-9]+(?:\.[0-9]+)?\s*(?:Mbits/sec|Gbits/sec))",
            sender_line,
            flags=re.IGNORECASE,
        )
        if m:
            res["transfer"] = m.group(1)
            res["bitrate"] = m.group(2)
            # Try to find any integer before 'sender' as retrans
            m2 = re.search(r"(\d+)\s+sender", sender_line, flags=re.IGNORECASE)
            if m2:
                res["retransmits"] = int(m2.group(1))
            return res
    else:
        res["transfer"] = m.group(1)
        res["bitrate"] = m.group(2)
        res["retransmits"] = int(m.group(3))
        return res

    # fallback: search generically for transfer, bitrate, retrans
    m_tr = re.search(
        r"([0-9]+(?:\.[0-9]+)?\s*(?:MBytes|GBytes))", sender_line, flags=re.IGNORECASE
    )
    m_br = re.search(
        r"([0-9]+(?:\.[0-9]+)?\s*(?:Mbits/sec|Gbits/sec))",
        sender_line,
        flags=re.IGNORECASE,
    )
    m_re = re.search(
        r"(\d+)\s*(?:retransmits|retransmits|retrans|retries)?",
        sender_line,
        flags=re.IGNORECASE,
    )
    if m_tr:
        res["transfer"] = m_tr.group(1)
    if m_br:
        res["bitrate"] = m_br.group(1)
    if m_re:
        try:
            res["retransmits"] = int(m_re.group(1))
        except Exception:
            res["retransmits"] = None
    return res


def scenario_throughput_baseline(net, hosts, verbose=False):
    """Skenario 1: Baseline throughput Host1 -> Host9"""
    h1 = hosts.get("h1")
    h9 = hosts.get("h9")
    result = {
        "scenario": "baseline",
        "transfer": None,
        "bitrate": None,
        "retransmits": None,
    }
    if not h1 or not h9:
        result["error"] = "hosts_missing"
        return result

    # Start server as daemon
    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("iperf3 -s -D")
    time.sleep(0.5)

    # Run client for 10s
    out = h1.cmd("iperf3 -c 10.0.0.9 -t 10")
    if verbose:
        print("iperf3 baseline output:\n", out)

    parsed = parse_iperf3_sender(out)
    result.update(
        {
            "transfer": parsed.get("transfer"),
            "bitrate": parsed.get("bitrate"),
            "retransmits": parsed.get("retransmits"),
        }
    )

    # cleanup
    h1.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    time.sleep(0.2)
    return result


def scenario_throughput_multiflow(net, hosts, verbose=False):
    """Skenario 2: Multi-flow stress test with three concurrent iperf3 flows"""
    h1 = hosts.get("h1")
    h2 = hosts.get("h2")
    h3 = hosts.get("h3")
    h9 = hosts.get("h9")
    h10 = hosts.get("h10")
    h11 = hosts.get("h11")
    result = {
        "scenario": "multiflow",
        "transfer": None,
        "bitrate": None,
        "retransmits": None,
    }
    if not (h1 and h2 and h3 and h9 and h10 and h11):
        result["error"] = "hosts_missing"
        return result

    # Start servers
    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    h10.cmd("killall -9 iperf3 2>/dev/null || true")
    h11.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("iperf3 -s -p 5201 -D")
    h10.cmd("iperf3 -s -p 5202 -D")
    h11.cmd("iperf3 -s -p 5203 -D")
    time.sleep(0.5)

    # Start clients in parallel
    p1 = h1.popen(
        "iperf3 -c 10.0.0.9 -p 5201 -t 15",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p2 = h2.popen(
        "iperf3 -c 10.0.0.10 -p 5202 -t 15",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p3 = h3.popen(
        "iperf3 -c 10.0.0.11 -p 5203 -t 15",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out1, err1 = p1.communicate()
    out2, err2 = p2.communicate()
    out3, err3 = p3.communicate()

    parsed = parse_iperf3_sender(out1)
    result.update(
        {
            "transfer": parsed.get("transfer"),
            "bitrate": parsed.get("bitrate"),
            "retransmits": parsed.get("retransmits"),
        }
    )

    # cleanup
    for h in (h1, h2, h3, h9, h10, h11):
        try:
            h.cmd("killall -9 iperf3 2>/dev/null || true")
        except Exception:
            pass
    time.sleep(0.2)
    return result


def scenario_throughput_failover(net, hosts, verbose=False):
    """Skenario 3: Throughput during failover (trigger link down mid-transmission)"""
    h1 = hosts.get("h1")
    h9 = hosts.get("h9")
    result = {
        "scenario": "failover",
        "transfer": None,
        "bitrate": None,
        "retransmits": None,
    }
    if not h1 or not h9:
        result["error"] = "hosts_missing"
        return result

    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("iperf3 -s -p 5204 -D")
    time.sleep(0.5)

    p = h1.popen(
        "iperf3 -c 10.0.0.9 -p 5204 -t 20",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(5)  # let TCP ramp up

    # trigger link failure
    try:
        net.configLinkStatus("Core1", "Core3", "down")
    except Exception:
        try:
            net.configLinkStatus("s1", "s3", "down")
        except Exception:
            pass

    out_bytes, err = p.communicate()
    parsed = parse_iperf3_sender(out_bytes)
    result.update(
        {
            "transfer": parsed.get("transfer"),
            "bitrate": parsed.get("bitrate"),
            "retransmits": parsed.get("retransmits"),
        }
    )

    # restore link
    try:
        net.configLinkStatus("Core1", "Core3", "up")
    except Exception:
        try:
            net.configLinkStatus("s1", "s3", "up")
        except Exception:
            pass

    # cleanup
    h1.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    time.sleep(0.2)
    return result


def scenario_throughput_mss_compare(net, hosts, verbose=False):
    """Skenario 4: Throughput compare for MSS 500 vs 1460"""
    h1 = hosts.get("h1")
    h9 = hosts.get("h9")
    result = {
        "scenario": "mss_compare",
        "small_transfer": None,
        "small_bitrate": None,
        "small_retransmits": None,
        "large_transfer": None,
        "large_bitrate": None,
        "large_retransmits": None,
    }
    if not h1 or not h9:
        result["error"] = "hosts_missing"
        return result

    h9.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("iperf3 -s -D")
    time.sleep(0.5)

    out_small = h1.cmd("iperf3 -c 10.0.0.9 -M 500 -t 10")
    if verbose:
        print("iperf3 MSS 500 output:\n", out_small)
    parsed_small = parse_iperf3_sender(out_small)

    out_large = h1.cmd("iperf3 -c 10.0.0.9 -M 1460 -t 10")
    if verbose:
        print("iperf3 MSS 1460 output:\n", out_large)
    parsed_large = parse_iperf3_sender(out_large)

    result.update(
        {
            "small_transfer": parsed_small.get("transfer"),
            "small_bitrate": parsed_small.get("bitrate"),
            "small_retransmits": parsed_small.get("retransmits"),
            "large_transfer": parsed_large.get("transfer"),
            "large_bitrate": parsed_large.get("bitrate"),
            "large_retransmits": parsed_large.get("retransmits"),
        }
    )

    # cleanup
    h1.cmd("killall -9 iperf3 2>/dev/null || true")
    h9.cmd("killall -9 iperf3 2>/dev/null || true")
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


def save_results(
    results,
    output_dir="results/hierarchy/throughput",
    algo_name="unknown",
    metric_name="throughput",
):
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ["scenario"] + sorted(k for k in keys if k != "scenario")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    return csv_path


def save_per_scenario_csvs(
    results,
    output_dir="results/hierarchy/throughput",
    algo_name="unknown",
    metric_name="throughput",
):
    os.makedirs(output_dir, exist_ok=True)
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ["scenario"] + sorted(k for k in keys if k != "scenario")
    paths = []
    for idx, row in enumerate(results, 1):
        path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, idx))
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerow(row)
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Throughput Measurement Experiment (Hierarchy)"
    )
    parser.add_argument(
        "--controller-cmd", help="Controller command to start", default=None
    )
    parser.add_argument(
        "--algo-name",
        help="Algorithm label for CSV filenames (e.g., dijkstra, astar)",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for results",
        default="results/hierarchy/throughput",
    )
    parser.add_argument(
        "--no-controller", help="Do not auto-start controller", action="store_true"
    )
    parser.add_argument("--verbose", help="Verbose logging", action="store_true")
    args = parser.parse_args(argv)
    metric_name = "throughput"
    algo_name = normalize_algo_name(
        args.algo_name or infer_algo_name(args.controller_cmd)
    )

    patch_resource_limits()
    cleanup_mininet()

    ctrl_proc = None
    if not args.no_controller and args.controller_cmd:
        ctrl_proc = start_controller(args.controller_cmd)

    net = build_network()
    try:
        net.start()
        hosts = find_hosts(net)
        if args.verbose:
            print("Hosts discovered:", [k for k, v in hosts.items() if v])

        results = []
        results.append(scenario_throughput_baseline(net, hosts, verbose=args.verbose))
        time.sleep(1)
        results.append(scenario_throughput_multiflow(net, hosts, verbose=args.verbose))
        time.sleep(1)
        results.append(scenario_throughput_failover(net, hosts, verbose=args.verbose))
        time.sleep(1)
        results.append(
            scenario_throughput_mss_compare(net, hosts, verbose=args.verbose)
        )

        csv_path = save_results(
            results,
            output_dir=args.output_dir,
            algo_name=algo_name,
            metric_name=metric_name,
        )
        save_per_scenario_csvs(
            results,
            output_dir=args.output_dir,
            algo_name=algo_name,
            metric_name=metric_name,
        )
        print("\nResults saved to:", csv_path)

    finally:
        try:
            # Ensure iperf3 processes killed on all hosts
            for h in net.hosts:
                try:
                    h.cmd("killall -9 iperf3 2>/dev/null || true")
                except Exception:
                    pass
        except Exception:
            pass
        try:
            net.stop()
        except Exception:
            pass
        stop_controller(ctrl_proc)


if __name__ == "__main__":
    main()
