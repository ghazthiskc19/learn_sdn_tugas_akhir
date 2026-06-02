#!/usr/bin/env python3
"""
Experiment 4: Hop Count Measurement (Hierarchy Topology)

Implements:
- get_hop_count(net, src_host, dst_host)
- main scenarios: progressive distances and rerouting (link failures)

Saves results to results/hopcount/hopcount_results.csv
"""

import argparse
import csv
import os
import resource
import subprocess
import sys
import time

from mininet.net import Mininet

# allow relative imports
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
        # HierarchyTopo uses 'Host1'..'Host12'; fallback alias 'h1'..'h12'
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
        hosts[alias] = node  # always keyed as h1..h12 for experiment logic
    return hosts


def del_all_flows(net):
    for sw in net.switches:
        try:
            sw.cmd("ovs-ofctl del-flows %s" % sw.name)
        except Exception:
            pass


def get_hop_count(net, src_host, dst_host, verbose=False):
    """Trigger a single ping to install flows and count switches that have matching flow entries.

    Steps:
    - Extract MAC addresses
    - Clear flows on all switches
    - Sleep(1)
    - Trigger single ping from src to dst
    - Dump flows on each switch and count switches containing both dl_src and dl_dst
    - Return int hop count
    """
    if src_host is None or dst_host is None:
        return None

    mac_src = src_host.MAC()
    mac_dst = dst_host.MAC()

    # Clear flows to ensure fresh installation
    del_all_flows(net)
    time.sleep(1)

    # trigger single ping
    try:
        src_host.cmd("ping -c 1 -W 1 %s" % dst_host.IP())
    except Exception:
        pass

    # Wait briefly for controller to install flows
    time.sleep(0.5)

    counter = 0
    for sw in net.switches:
        try:
            out = sw.cmd("ovs-ofctl dump-flows %s" % sw.name)
        except Exception:
            out = ""
        # Normalize MAC formats to lowercase
        if out and mac_src and mac_dst:
            if ("dl_src=%s" % mac_src.lower()) in out.lower() and (
                "dl_dst=%s" % mac_dst.lower()
            ) in out.lower():
                counter += 1
                if verbose:
                    print("Match on switch", sw.name)

    return counter


def run_progressive_distances(net, hosts, verbose=False):
    results = []
    pairs = [
        ("h1", "h2"),  # close (same access)
        ("h1", "h3"),  # medium
        ("h1", "h5"),  # far (via core)
        ("h1", "h7"),  # further
    ]
    for src, dst in pairs:
        src_h = hosts.get(src)
        dst_h = hosts.get(dst)
        hop = get_hop_count(net, src_h, dst_h, verbose=verbose)
        results.append(
            {"test": "progressive", "src": src, "dst": dst, "hop_count": hop}
        )
        if verbose:
            print("Progressive:", src, "->", dst, "hops=", hop)
        time.sleep(0.5)
    return results


def run_reroute_scenario(net, hosts, verbose=False):
    results = []
    src = hosts.get("h1")
    dst = hosts.get("h9")
    baseline = get_hop_count(net, src, dst, verbose=verbose)
    results.append(
        {
            "test": "reroute",
            "phase": "baseline",
            "src": "h1",
            "dst": "h9",
            "hop_count": baseline,
        }
    )

    # Core failure
    try:
        net.configLinkStatus("Core1", "Core3", "down")
    except Exception:
        try:
            net.configLinkStatus("s1", "s3", "down")
        except Exception:
            pass
    time.sleep(1)
    core_fail = get_hop_count(net, src, dst, verbose=verbose)
    results.append(
        {
            "test": "reroute",
            "phase": "core_failure",
            "src": "h1",
            "dst": "h9",
            "hop_count": core_fail,
        }
    )

    # Distribution failure: Access1-Dist1 down
    time.sleep(2)
    try:
        net.configLinkStatus("Access1", "Dist1", "down")
    except Exception:
        # try generic names
        try:
            net.configLinkStatus("s1", "s2", "down")
        except Exception:
            pass
    time.sleep(1)
    dist_fail = get_hop_count(net, src, dst, verbose=verbose)
    results.append(
        {
            "test": "reroute",
            "phase": "dist_failure",
            "src": "h1",
            "dst": "h9",
            "hop_count": dist_fail,
        }
    )

    # Restore all links up
    try:
        net.configLinkStatus("Core1", "Core3", "up")
    except Exception:
        try:
            net.configLinkStatus("s1", "s3", "up")
        except Exception:
            pass
    try:
        net.configLinkStatus("Access1", "Dist1", "up")
    except Exception:
        try:
            net.configLinkStatus("s1", "s2", "up")
        except Exception:
            pass

    # Clear flows
    del_all_flows(net)
    return results


def normalize_algo_name(value):
    if not value:
        return "unknown"
    return value.strip().replace(" ", "_").replace("-", "_").lower()


def build_csv_name(algo_name, metric_name, scenario_idx):
    algo_name = normalize_algo_name(algo_name)
    metric_name = normalize_algo_name(metric_name)
    return f"{algo_name}_{metric_name}_{scenario_idx}.csv"


def save_results(
    results,
    output_dir="results/hierarchy/hopcount",
    algo_name="unknown",
    metric_name="hopcount",
):
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ["test"] + [k for k in sorted(keys) if k != "test"]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    return path


def save_per_scenario_csvs(
    results,
    output_dir="results/hierarchy/hopcount",
    algo_name="unknown",
    metric_name="hopcount",
):
    os.makedirs(output_dir, exist_ok=True)
    keys = set()
    for r in results:
        keys.update(r.keys())
    keys = ["test"] + [k for k in sorted(keys) if k != "test"]
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
        description="Hop Count Measurement Experiment (Hierarchy)"
    )
    parser.add_argument(
        "--algo-name",
        help="Algorithm label for CSV filenames (e.g., dijkstra, astar)",
        default=None,
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for results",
        default="results/hierarchy/hopcount",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose")
    args = parser.parse_args(argv)
    metric_name = "hopcount"
    algo_name = normalize_algo_name(args.algo_name)

    patch_resource_limits()
    cleanup_mininet()
    net = build_network()
    try:
        net.start()
        hosts = find_hosts(net)
        if args.verbose:
            print("Hosts:", [k for k, v in hosts.items() if v])

        results = []
        results.extend(run_progressive_distances(net, hosts, verbose=args.verbose))
        time.sleep(1)
        results.extend(run_reroute_scenario(net, hosts, verbose=args.verbose))

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
            del_all_flows(net)
        except Exception:
            pass
        try:
            net.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
