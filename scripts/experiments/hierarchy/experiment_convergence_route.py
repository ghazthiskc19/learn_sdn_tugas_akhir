#!/usr/bin/env python3
"""
Route Convergence Time Measurement Experiment

Mengukur waktu konvergensi rute pada topology hierarchy dengan berbagai skenario:
1. Cold-Start Convergence (Inisialisasi Awal)
2. Core Failure Convergence (Backbone Link Down)
3. Edge Failure Convergence (Access Link Down)
4. Node Failure Convergence (Distribution Switch Down)

Target route: Host1 (10.0.0.1) → Host9 (10.0.0.9)
"""

import argparse
import csv
import os
import resource
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


class HierarchyTopo(Topo):
    """3-tier hierarchy topology: Core - Distribution - Access"""

    def addSwitch(self, name, **opts):
        kwargs = {"protocols": "OpenFlow13"}
        kwargs.update(opts)
        return super(HierarchyTopo, self).addSwitch(name, **opts)

    def __init__(self):
        Topo.__init__(self)

        info("*** Adding hosts\n")
        h = {}
        for i in range(1, 13):
            h[i] = self.addHost(f"Host{i}", ip=f"10.0.0.{i}/24")

        info("*** Adding switches\n")
        # Core layer
        core1 = self.addSwitch("Core1", dpid="0000000000000001")
        core2 = self.addSwitch("Core2", dpid="0000000000000002")
        core3 = self.addSwitch("Core3", dpid="0000000000000003")

        # Distribution layer
        dist1 = self.addSwitch("Dist1", dpid="0000000000000004")
        dist2 = self.addSwitch("Dist2", dpid="0000000000000005")
        dist3 = self.addSwitch("Dist3", dpid="0000000000000006")
        dist4 = self.addSwitch("Dist4", dpid="0000000000000007")
        dist5 = self.addSwitch("Dist5", dpid="0000000000000008")
        dist6 = self.addSwitch("Dist6", dpid="0000000000000009")

        # Access layer
        acc1 = self.addSwitch("Access1", dpid="0000000000000010")
        acc2 = self.addSwitch("Access2", dpid="0000000000000011")
        acc3 = self.addSwitch("Access3", dpid="0000000000000012")
        acc4 = self.addSwitch("Access4", dpid="0000000000000013")
        acc5 = self.addSwitch("Access5", dpid="0000000000000014")
        acc6 = self.addSwitch("Access6", dpid="0000000000000015")

        info("*** Adding host links\n")
        # Host to Access links
        self.addLink(h[1], acc1, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[2], acc1, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[3], acc2, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[4], acc2, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[5], acc3, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[6], acc3, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[7], acc4, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[8], acc4, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[9], acc5, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[10], acc5, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[11], acc6, bw=100, delay="2ms", use_hfsc=True)
        self.addLink(h[12], acc6, bw=100, delay="2ms", use_hfsc=True)

        info("*** Adding Access-Distribution links\n")
        # Access1 to Dist1 and Dist2
        self.addLink(acc1, dist1, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc1, dist2, bw=500, delay="1ms", use_hfsc=True)
        # Access2 to Dist1 and Dist2
        self.addLink(acc2, dist1, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc2, dist2, bw=500, delay="1ms", use_hfsc=True)
        # Access3 to Dist3 and Dist4
        self.addLink(acc3, dist3, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc3, dist4, bw=500, delay="1ms", use_hfsc=True)
        # Access4 to Dist3 and Dist4
        self.addLink(acc4, dist3, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc4, dist4, bw=500, delay="1ms", use_hfsc=True)
        # Access5 to Dist5 and Dist6
        self.addLink(acc5, dist5, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc5, dist6, bw=500, delay="1ms", use_hfsc=True)
        # Access6 to Dist5 and Dist6
        self.addLink(acc6, dist5, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(acc6, dist6, bw=500, delay="1ms", use_hfsc=True)

        info("*** Adding Distribution-Distribution links\n")
        # Within region
        self.addLink(dist1, dist2, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(dist3, dist4, bw=500, delay="1ms", use_hfsc=True)
        self.addLink(dist5, dist6, bw=500, delay="1ms", use_hfsc=True)

        info("*** Adding Distribution-Core links\n")
        # Distribution to Core
        self.addLink(dist1, core1, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(dist2, core1, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(dist3, core2, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(dist4, core2, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(dist5, core3, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(dist6, core3, bw=1000, delay="0.5ms", use_hfsc=True)

        info("*** Adding Core backbone links\n")
        # Core backbone (full mesh)
        self.addLink(core1, core2, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(core2, core3, bw=1000, delay="0.5ms", use_hfsc=True)
        self.addLink(core1, core3, bw=1000, delay="0.5ms", use_hfsc=True)


def measure_convergence_route(src_host, dst_ip, max_retries=15, verbose=False):
    """
    Mengukur waktu konvergensi rute dengan mengirim ping berulang.

    Args:
        src_host: Host sumber (Mininet Host object)
        dst_ip: IP address tujuan (string)
        max_retries: Jumlah maksimal percobaan ping
        verbose: Print debug info

    Returns:
        convergence_time (float): Waktu konvergensi dalam detik
        None: Jika gagal dalam max_retries attempts
    """
    start_time = time.time()

    for attempt in range(max_retries):
        # Kirim single ping dengan timeout 1 detik
        result = src_host.cmd(f"ping -c 1 -W 1 {dst_ip}")

        if verbose:
            info(f"  [Attempt {attempt + 1}] ping result: {len(result)} bytes\n")

        # Cek apakah ping berhasil (ada "1 received" atau "bytes from")
        if "1 received" in result or "bytes from" in result:
            end_time = time.time()
            convergence_time = end_time - start_time
            if verbose:
                info(
                    f"  ✓ Convergence achieved in {convergence_time:.3f}s at attempt {attempt + 1}\n"
                )
            return convergence_time

        # Tunggu sebentar sebelum retry
        time.sleep(0.1)

    # Timeout: tidak convergence dalam max_retries
    if verbose:
        info(f"  ✗ Convergence FAILED after {max_retries} attempts\n")
    return None


def run_experiment(net, host1, host9_ip, controller_log_path=None):
    """
    Jalankan 4 skenario pengukuran route convergence.

    Returns:
        List of tuples: (scenario_name, convergence_time)
    """
    results = []

    # ========== Skenario 1: Cold-Start Convergence ==========
    print("\n" + "=" * 70)
    print("SKENARIO 1: Cold-Start Convergence (Inisialisasi Awal)")
    print("=" * 70)

    print("  Aksi: Jaringan di-start, tunggu 3 detik untuk inisialisasi LLDP...")
    time.sleep(3)

    print("  Pengukuran: Mengirim ping dari Host1 ke Host9...")
    conv_time = measure_convergence_route(host1, host9_ip, max_retries=15, verbose=True)

    if conv_time is not None:
        print(f"  ✓ Cold-Start Convergence Time: {conv_time:.3f}s")
        results.append(("Cold-Start", conv_time))
    else:
        print("  ✗ Cold-Start Convergence: TIMEOUT (None)")
        results.append(("Cold-Start", None))

    # ========== Skenario 2: Core Failure Convergence ==========
    print("\n" + "=" * 70)
    print("SKENARIO 2: Core Failure Convergence (Core1-Core3 Link Down)")
    print("=" * 70)

    print("  Aksi: Tunggu 2 detik, lalu putuskan link Core1-Core3...")
    time.sleep(2)

    print("  Memutuskan link Core1 <-> Core3...")
    net.configLinkStatus("Core1", "Core3", "down")

    print("  Pengukuran: Mengirim ping dari Host1 ke Host9...")
    conv_time = measure_convergence_route(host1, host9_ip, max_retries=15, verbose=True)

    if conv_time is not None:
        print(f"  ✓ Core Failure Convergence Time: {conv_time:.3f}s")
        results.append(("Core Failure", conv_time))
    else:
        print("  ✗ Core Failure Convergence: TIMEOUT (None)")
        results.append(("Core Failure", None))

    # Restore link
    print("  Mengembalikan link Core1 <-> Core3...")
    net.configLinkStatus("Core1", "Core3", "up")
    time.sleep(1)

    # ========== Skenario 3: Edge Failure Convergence ==========
    print("\n" + "=" * 70)
    print("SKENARIO 3: Edge Failure Convergence (Access1-Dist1 Link Down)")
    print("=" * 70)

    print("  Aksi: Tunggu 2 detik, lalu putuskan link Access1-Dist1...")
    time.sleep(2)

    print("  Memutuskan link Access1 <-> Dist1...")
    net.configLinkStatus("Access1", "Dist1", "down")

    print("  Pengukuran: Mengirim ping dari Host1 ke Host9...")
    conv_time = measure_convergence_route(host1, host9_ip, max_retries=15, verbose=True)

    if conv_time is not None:
        print(f"  ✓ Edge Failure Convergence Time: {conv_time:.3f}s")
        results.append(("Edge Failure", conv_time))
    else:
        print("  ✗ Edge Failure Convergence: TIMEOUT (None)")
        results.append(("Edge Failure", None))

    # Restore link
    print("  Mengembalikan link Access1 <-> Dist1...")
    net.configLinkStatus("Access1", "Dist1", "up")
    time.sleep(1)

    # ========== Skenario 4: Node Failure Convergence ==========
    print("\n" + "=" * 70)
    print("SKENARIO 4: Node Failure Convergence (Dist2 Switch Down)")
    print("=" * 70)

    print(
        "  Aksi: Tunggu 2 detik, lalu simulasikan Dist2 down dengan memutus semua linknya..."
    )
    time.sleep(2)

    print("  Memutuskan semua link Dist2:")
    print("    - Dist2 <-> Core1")
    net.configLinkStatus("Dist2", "Core1", "down")

    print("    - Dist2 <-> Access1")
    net.configLinkStatus("Dist2", "Access1", "down")

    print("    - Dist2 <-> Access2")
    net.configLinkStatus("Dist2", "Access2", "down")

    print("  Pengukuran: Mengirim ping dari Host1 ke Host9...")
    conv_time = measure_convergence_route(host1, host9_ip, max_retries=15, verbose=True)

    if conv_time is not None:
        print(f"  ✓ Node Failure Convergence Time: {conv_time:.3f}s")
        results.append(("Node Failure", conv_time))
    else:
        print("  ✗ Node Failure Convergence: TIMEOUT (None)")
        results.append(("Node Failure", None))

    # Restore all Dist2 links
    print("  Mengembalikan semua link Dist2...")
    net.configLinkStatus("Dist2", "Core1", "up")
    net.configLinkStatus("Dist2", "Access1", "up")
    net.configLinkStatus("Dist2", "Access2", "up")
    time.sleep(1)

    return results


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


def save_results_to_csv(
    results,
    output_dir="results/hierarchy/convergence",
    algo_name="unknown",
    metric_name="convergence",
):
    """Simpan hasil pengukuran ke file CSV."""
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, 0))

    print(f"\n{'=' * 70}")
    print("Menyimpan hasil ke CSV...")
    print(f"{'=' * 70}")

    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Scenario", "Convergence_Time_Seconds", "Status"])

        for scenario, conv_time in results:
            status = "SUCCESS" if conv_time is not None else "TIMEOUT"
            conv_time_str = f"{conv_time:.3f}" if conv_time is not None else "None"
            writer.writerow([scenario, conv_time_str, status])

    print(f"✓ Hasil disimpan ke: {csv_path}")
    return csv_path


def save_per_scenario_csvs(
    results,
    output_dir="results/hierarchy/convergence",
    algo_name="unknown",
    metric_name="convergence",
):
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for idx, (scenario, conv_time) in enumerate(results, 1):
        status = "SUCCESS" if conv_time is not None else "TIMEOUT"
        conv_time_str = f"{conv_time:.3f}" if conv_time is not None else "None"
        path = os.path.join(output_dir, build_csv_name(algo_name, metric_name, idx))
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Scenario", "Convergence_Time_Seconds", "Status"])
            writer.writerow([scenario, conv_time_str, status])
        paths.append(path)
    return paths


def print_summary(results):
    """Print ringkasan hasil pengukuran."""
    print(f"\n{'=' * 70}")
    print("RINGKASAN HASIL PENGUKURAN ROUTE CONVERGENCE TIME")
    print(f"{'=' * 70}")
    print(f"{'Scenario':<25} {'Convergence Time':<20} {'Status':<15}")
    print("-" * 70)

    for scenario, conv_time in results:
        if conv_time is not None:
            time_str = f"{conv_time:.3f}s"
            status = "✓ SUCCESS"
        else:
            time_str = "N/A"
            status = "✗ TIMEOUT"
        print(f"{scenario:<25} {time_str:<20} {status:<15}")

    # Calculate statistics
    valid_times = [t for _, t in results if t is not None]
    if valid_times:
        print(f"\n{'Statistik:':<25}")
        print(f"  - Min Convergence:  {min(valid_times):.3f}s")
        print(f"  - Max Convergence:  {max(valid_times):.3f}s")
        print(f"  - Avg Convergence:  {sum(valid_times) / len(valid_times):.3f}s")
        print(f"  - Success Rate:     {len(valid_times)}/{len(results)} scenarios")

    print(f"{'=' * 70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Route Convergence Time Measurement Experiment on Hierarchy Topology"
    )
    parser.add_argument(
        "--controller-cmd",
        default="python3 SPF/dijkstra_osken_controller.py --verbose",
        help="Controller command to start",
    )
    parser.add_argument(
        "--algo-name",
        default=None,
        help="Algorithm label for CSV filenames (e.g., dijkstra, astar)",
    )
    parser.add_argument(
        "--output-dir",
        default="results/hierarchy/convergence",
        help="Output directory for results",
    )
    parser.add_argument(
        "--no-controller",
        action="store_true",
        help="Skip starting controller (for manual testing)",
    )

    args = parser.parse_args()
    metric_name = "convergence"
    algo_name = normalize_algo_name(
        args.algo_name or infer_algo_name(args.controller_cmd)
    )

    # Disable excessive logging
    setLogLevel("info")

    print("=" * 70)
    print("ROUTE CONVERGENCE TIME MEASUREMENT EXPERIMENT")
    print("Target: Host1 (10.0.0.1) → Host9 (10.0.0.9)")
    print("Topology: Hierarchy (15 switches, 12 hosts)")
    print("=" * 70)

    # Start controller if requested
    if not args.no_controller:
        print(f"\nStarting controller: {args.controller_cmd}")
        import shlex
        import subprocess

        ctrl_proc = subprocess.Popen(
            shlex.split(args.controller_cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("✓ Controller started, waiting 2 seconds for initialization...")
        time.sleep(2)
    else:
        ctrl_proc = None

    patch_resource_limits()
    cleanup_mininet()

    # Create topology and network
    print("\nCreating Mininet network...")
    topo = HierarchyTopo()
    net = Mininet(
        topo=topo,
        controller=partial(RemoteController, ip="127.0.0.1", port=6633),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        waitConnected=True,
    )

    # Disable IPv6
    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")
    for sw in net.switches:
        sw.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")

    print("✓ Network created")

    # Start network
    print("\nStarting network...")
    net.start()

    info("\n*** Network is running ***\n")
    dumpNodeConnections(net.hosts)

    # Get hosts
    host1 = net.get("Host1")
    host9_ip = "10.0.0.9"

    # Run experiment scenarios
    try:
        results = run_experiment(net, host1, host9_ip)

        # Print summary
        print_summary(results)

        # Save to CSV
        csv_path = save_results_to_csv(
            results, args.output_dir, algo_name=algo_name, metric_name=metric_name
        )
        save_per_scenario_csvs(
            results, args.output_dir, algo_name=algo_name, metric_name=metric_name
        )
        print(f"Results saved to: {csv_path}\n")

    except Exception as e:
        print(f"\n✗ Error during experiment: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        print("\nCleaning up...")
        try:
            net.stop()
        except Exception:
            pass
        if ctrl_proc:
            try:
                ctrl_proc.terminate()
                ctrl_proc.wait(timeout=3)
            except Exception:
                try:
                    ctrl_proc.kill()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
