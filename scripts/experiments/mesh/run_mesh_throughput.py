#!/usr/bin/env python3
"""Mesh throughput benchmark for SPF controllers.

Runs the Mesh topology against BFS, A*, Bellman-Ford, and Dijkstra.
Measures TCP throughput from HostA to HostD using iperf3 for 20s with 1s
interval reporting. Weighted controllers use `bandwidth_mbps` metric.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import RemoteController
import re


ROOT_DIR = Path(__file__).resolve().parents[3]
SPF_DIR = ROOT_DIR / "SPF"
RESULTS_DIR = ROOT_DIR / "scripts" / "experiments" / "results" / "mesh"
TOPOLOGY_FILE = SPF_DIR / "topology-mesh.py"

SOURCE_HOST = "HostA"
DEST_HOST = "HostD"
DEST_IP = "10.0.0.4"
SOURCE_SWITCH_DPID = 1
DEST_SWITCH_DPID = 4

IPERF_DURATION = 20
IPERF_INTERVAL = 1
WARMUP_PING_COUNT = 10
OFP_BASE_PORT = 6633

DEFAULT_ALGORITHMS = ["bfs", "astar", "bellman-ford", "dijkstra"]
ALGORITHM_CONTROLLERS = {
    "bfs": SPF_DIR / "bfs_osken_controller.py",
    "astar": SPF_DIR / "astar_osken_controller.py",
    "bellman-ford": SPF_DIR / "bellman_ford_osken_controller.py",
    "dijkstra": SPF_DIR / "dijkstra_osken_controller.py",
}


@dataclass
class ThroughputSample:
    algorithm: str
    controller: str
    second: int
    bits_per_second: float
    path: str
    hop_count: int
    total_bandwidth_mbps: float


def load_topology_class():
    spec = importlib.util.spec_from_file_location("topology_mesh", TOPOLOGY_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load topology from {TOPOLOGY_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MeshTopo


def build_bandwidth_weights() -> Dict[str, Dict[str, float]]:
    """Return bandwidth map for the mesh topology.

    Make the direct link 1:4 a lower-bandwidth path to create divergence.
    """
    links = {
        "1:2": {"bandwidth_mbps": 500},
        "1:3": {"bandwidth_mbps": 500},
        "1:4": {"bandwidth_mbps": 50},  # direct A-D is constrained
        "2:3": {"bandwidth_mbps": 500},
        "2:4": {"bandwidth_mbps": 500},
        "3:4": {"bandwidth_mbps": 500},
    }
    return {"links": links}


def write_bandwidth_weights(path: Path) -> None:
    path.write_text(json.dumps(build_bandwidth_weights(), indent=2, sort_keys=True) + "\n")


def mininet_cleanup() -> None:
    """Best-effort cleanup to remove stale Mininet/OVS state."""
    subprocess.run(
        ["mn", "-c"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def get_free_tcp_port(start_port: int = OFP_BASE_PORT) -> int:
    """Find an available localhost TCP port, preferring >= start_port."""
    for port in range(start_port, start_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# Mapping for readable switch labels used in output
SWITCH_LABELS = {
    1: "SwitchA",
    2: "SwitchB",
    3: "SwitchC",
    4: "SwitchD",
}

PATH_NODE_RE = re.compile(r"s(\d+)")


def parse_path_nodes(path: str) -> List[int]:
    return [int(m) for m in PATH_NODE_RE.findall(path)]


def normalize_path_direction(path: str, expected_src: int, expected_dst: int) -> str:
    nodes = parse_path_nodes(path)
    if len(nodes) < 2:
        return path
    if nodes[0] == expected_dst and nodes[-1] == expected_src:
        rev = list(reversed(nodes))
        return " -> ".join(f"s{n}" for n in rev)
    return path


def format_path_labels(path: str) -> str:
    nodes = parse_path_nodes(path)
    labels = [SWITCH_LABELS.get(n, f"s{n}") for n in nodes]
    return " -> ".join(labels)


def wait_for_controller(port: int = OFP_BASE_PORT, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"controller did not open 127.0.0.1:{port} within {timeout}s")


def start_controller(
    algorithm: str,
    controller_path: Path,
    weights_file: Path,
    ofp_port: int,
) -> tuple[subprocess.Popen, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"mesh_thr_{algorithm}_"))
    log_path = temp_dir / "controller.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if algorithm != "bfs":
        env["SPF_WEIGHTS_FILE"] = str(weights_file)
        env["SPF_WEIGHT_FIELD"] = "bandwidth_mbps"

    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            str(controller_path),
            "--verbose",
            "--ofp-tcp-listen-port",
            str(ofp_port),
        ],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env,
    )
    process._log_handle = log_handle  # type: ignore[attr-defined]
    return process, log_path


def stop_controller(process: subprocess.Popen) -> None:
    log_handle = getattr(process, "_log_handle", None)
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    finally:
        if log_handle is not None:
            log_handle.close()


def run_single_algorithm(algorithm: str, weights_file: Path, ofp_port: int) -> List[ThroughputSample]:
    controller_path = ALGORITHM_CONTROLLERS[algorithm]
    controller_process, controller_log_path = start_controller(
        algorithm,
        controller_path,
        weights_file,
        ofp_port,
    )
    wait_for_controller(port=ofp_port)

    topology_cls = load_topology_class()
    topo = topology_cls()
    net = Mininet(
        topo=topo,
        controller=partial(RemoteController, ip="127.0.0.1", port=ofp_port),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        waitConnected=True,
    )

    samples: List[ThroughputSample] = []
    pre_stop_log_text = ""
    try:
        net.start()
        src_host, dst_host = net.get(SOURCE_HOST, DEST_HOST)

        # Warm-up ping to trigger flow installs
        src_host.cmd(f"ping -c {WARMUP_PING_COUNT} -W 1 {DEST_IP} >/dev/null 2>&1")
        time.sleep(1)

        # Start iperf3 server on destination
        dst_host.cmd("killall -q iperf3 || true")
        dst_host.cmd("iperf3 -s -D")

        # Run client and capture JSON output
        cmd = f"iperf3 -c {DEST_IP} -t {IPERF_DURATION} -i {IPERF_INTERVAL} -J"
        raw = src_host.cmd(cmd)
        try:
            j = json.loads(raw)
        except Exception:
            j = {}

        # Stop server
        dst_host.cmd("killall -q iperf3 || true")

        # Capture controller logs before teardown
        pre_stop_log_text = controller_log_path.read_text(encoding="utf-8", errors="ignore")
    finally:
        net.stop()
        stop_controller(controller_process)

    # Parse path installed from controller logs (best-effort)
    path = ""
    hop_count = 0
    total_bw = 0.0
    if pre_stop_log_text:
        for line in pre_stop_log_text.splitlines():
            if "[FLOW-INSTALL]" in line:
                parts = line.split(":")
                if len(parts) >= 3:
                    path = parts[-1].strip()
                    break

    if path:
        raw_path = normalize_path_direction(path, SOURCE_SWITCH_DPID, DEST_SWITCH_DPID)
        formatted = format_path_labels(raw_path)
        path = formatted
        nodes = parse_path_nodes(raw_path)
        hop_count = max(0, len(nodes) - 1)

    # Extract per-interval throughput from iperf3 JSON
    if isinstance(j, dict) and "intervals" in j:
        for i, interval in enumerate(j.get("intervals", []), start=1):
            bits = 0.0
            sum_stats = interval.get("sum", {})
            bits = float(sum_stats.get("bits_per_second", 0.0))
            samples.append(
                ThroughputSample(
                    algorithm=algorithm,
                    controller=controller_path.name,
                    second=i,
                    bits_per_second=bits,
                    path=path,
                    hop_count=hop_count,
                    total_bandwidth_mbps=total_bw,
                )
            )

    return samples


def write_csv(rows: Iterable[Dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        raise RuntimeError("no rows to write")
    fieldnames = list(rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Mesh throughput benchmark")
    parser.add_argument(
        "--output",
        default=str(RESULTS_DIR / "mesh_throughput.csv"),
        help="Path to the CSV output file",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=DEFAULT_ALGORITHMS,
        choices=DEFAULT_ALGORITHMS,
        help="Algorithms to run",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retries per algorithm on failure",
    )
    args = parser.parse_args()

    setLogLevel("warning")
    output_path = Path(args.output)

    with tempfile.TemporaryDirectory(prefix="mesh_weights_") as temp_dir:
        weights_file = Path(temp_dir) / "mesh_bw_weights.json"
        write_bandwidth_weights(weights_file)
        all_rows: List[Dict[str, object]] = []
        for algorithm in args.algorithms:
            last_error: Optional[Exception] = None
            samples: List[ThroughputSample] = []
            for attempt in range(1, args.retries + 1):
                mininet_cleanup()
                ofp_port = get_free_tcp_port()
                try:
                    samples = run_single_algorithm(algorithm, weights_file, ofp_port)
                    if len(samples) != IPERF_DURATION:
                        raise RuntimeError(
                            f"expected {IPERF_DURATION} samples, got {len(samples)}"
                        )
                    break
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    print(
                        f"[WARN] {algorithm} failed attempt {attempt}/{args.retries}: {exc}",
                        file=sys.stderr,
                    )
                    mininet_cleanup()

            if not samples:
                raise RuntimeError(f"algorithm {algorithm} failed after retries: {last_error}")

            for s in samples:
                all_rows.append(
                    {
                        "algorithm": s.algorithm,
                        "controller": s.controller,
                        "second": s.second,
                        "bits_per_second": s.bits_per_second,
                        "path": s.path,
                        "hop_count": s.hop_count,
                        "total_bandwidth_mbps": s.total_bandwidth_mbps,
                    }
                )

        expected_rows = len(args.algorithms) * IPERF_DURATION
        if len(all_rows) != expected_rows:
            raise RuntimeError(
                f"incomplete output: got {len(all_rows)} rows, expected {expected_rows}"
            )

        write_csv(all_rows, output_path)

    print(f"Wrote {len(all_rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
