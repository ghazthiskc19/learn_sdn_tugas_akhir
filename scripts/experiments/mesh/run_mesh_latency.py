#!/usr/bin/env python3
"""Mesh latency benchmark for SPF controllers.

Runs the Mesh topology against BFS, A*, Bellman-Ford, and Dijkstra.
For each algorithm it captures 50 ICMP RTT samples from HostA to HostD,
keeps all raw samples, marks the first 5 as warm-up, and stores everything
into one CSV file.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import re
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


ROOT_DIR = Path(__file__).resolve().parents[3]
SPF_DIR = ROOT_DIR / "SPF"
RESULTS_DIR = ROOT_DIR / "scripts" / "experiments" / "results" / "mesh"
TOPOLOGY_FILE = SPF_DIR / "topology-mesh.py"

SOURCE_HOST = "HostA"
DEST_HOST = "HostD"
DEST_IP = "10.0.0.4"
SOURCE_SWITCH_DPID = 1
DEST_SWITCH_DPID = 4

PING_COUNT = 50
WARMUP_DROP = 5
PING_INTERVAL = 0.2

DEFAULT_ALGORITHMS = ["bfs", "astar", "bellman-ford", "dijkstra"]
ALGORITHM_CONTROLLERS = {
    "bfs": SPF_DIR / "bfs_osken_controller.py",
    "astar": SPF_DIR / "astar_osken_controller.py",
    "bellman-ford": SPF_DIR / "bellman_ford_osken_controller.py",
    "dijkstra": SPF_DIR / "dijkstra_osken_controller.py",
}

PATH_RE = re.compile(r"\[PATH-COMPUTED\]\s+(?:\S+\s+)?s(\d+)(?:->|→)s(\d+):\s+(\d+)\s+hop\(s\)\s+path=(.+)")
PING_RE = re.compile(r"icmp_seq=(\d+).+time=([0-9.]+)\s*ms")

SWITCH_LABELS = {
    1: "SwitchA",
    2: "SwitchB",
    3: "SwitchC",
    4: "SwitchD",
}


@dataclass
class ExperimentResult:
    algorithm: str
    controller: str
    path: str
    hop_count: int
    total_delay_ms: float
    rows: List[Dict[str, object]]


def load_topology_class():
    spec = importlib.util.spec_from_file_location("topology_mesh", TOPOLOGY_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load topology from {TOPOLOGY_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MeshTopo


def build_delay_weights() -> Dict[str, Dict[str, float]]:
    """Return mesh delay map where A-D direct link has the highest delay."""
    links = {
        "1:2": {"delay_ms": 1.0},
        "1:3": {"delay_ms": 1.0},
        "1:4": {"delay_ms": 50.0},
        "2:3": {"delay_ms": 1.0},
        "2:4": {"delay_ms": 1.0},
        "3:4": {"delay_ms": 1.0},
    }
    return {"links": links}


def write_delay_weights(path: Path) -> None:
    path.write_text(json.dumps(build_delay_weights(), indent=2, sort_keys=True) + "\n")


def wait_for_controller(port: int = 6633, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"controller did not open 127.0.0.1:{port} within {timeout}s")


def parse_path_log(
    log_text: str,
    expected_src: Optional[int] = None,
    expected_dst: Optional[int] = None,
) -> Optional[Dict[str, object]]:
    matches = PATH_RE.findall(log_text)
    if not matches:
        return None

    selected = None
    for src, dst, hops, path in matches:
        if expected_src is not None and expected_dst is not None:
            if int(src) == expected_src and int(dst) == expected_dst:
                selected = (src, dst, hops, path)
                break
    if selected is None:
        selected = matches[-1]

    src, dst, hops, path = selected
    return {
        "src_switch": int(src),
        "dst_switch": int(dst),
        "hop_count": int(hops),
        "path": path.strip(),
    }


def parse_ping_output(output: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for line in output.splitlines():
        match = PING_RE.search(line)
        if not match:
            continue
        seq = int(match.group(1))
        rtt_ms = float(match.group(2))
        rows.append(
            {
                "icmp_seq": seq,
                "rtt_ms": rtt_ms,
                "raw_line": line.strip(),
            }
        )
    return rows


def parse_path_nodes(path: str) -> List[int]:
    return [int(node) for node in re.findall(r"s(\d+)", path)]


def normalize_path_direction(path: str, expected_src: int, expected_dst: int) -> str:
    nodes = parse_path_nodes(path)
    if len(nodes) < 2:
        return path
    if nodes[0] == expected_dst and nodes[-1] == expected_src:
        rev = list(reversed(nodes))
        return " -> ".join(f"s{node}" for node in rev)
    return path


def format_path_labels(path: str) -> str:
    nodes = parse_path_nodes(path)
    return " -> ".join(SWITCH_LABELS.get(node, f"s{node}") for node in nodes)


def parse_flow_install_log(log_text: str, src_mac: str, dst_mac: str) -> Optional[str]:
    pattern = re.compile(
        rf"\[FLOW-INSTALL\]\s+{re.escape(src_mac.lower())}\s+→\s+{re.escape(dst_mac.lower())}:\s+(.+)",
        re.IGNORECASE,
    )
    matches = pattern.findall(log_text)
    if not matches:
        return None
    return matches[0].strip()


def compute_path_delay(path: str, delay_weights: Dict[str, Dict[str, float]]) -> float:
    nodes = parse_path_nodes(path)
    if len(nodes) < 2:
        return 0.0
    total = 0.0
    links = delay_weights.get("links", {})
    for src, dst in zip(nodes[:-1], nodes[1:]):
        key = f"{min(src, dst)}:{max(src, dst)}"
        total += float(links.get(key, {}).get("delay_ms", 0.0))
    return total


def start_controller(algorithm: str, controller_path: Path, weights_file: Path) -> tuple[subprocess.Popen, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"mesh_{algorithm}_"))
    log_path = temp_dir / "controller.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if algorithm != "bfs":
        env["SPF_WEIGHTS_FILE"] = str(weights_file)
        env["SPF_WEIGHT_FIELD"] = "delay_ms"

    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(controller_path), "--verbose"],
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


def disable_ipv6(net: Mininet) -> None:
    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")
    for switch in net.switches:
        switch.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")


def run_single_algorithm(algorithm: str, delay_weights: Dict[str, Dict[str, float]], weights_file: Path) -> ExperimentResult:
    controller_path = ALGORITHM_CONTROLLERS[algorithm]
    controller_process, controller_log_path = start_controller(algorithm, controller_path, weights_file)
    wait_for_controller()

    topology_cls = load_topology_class()
    topo = topology_cls()
    net = Mininet(
        topo=topo,
        controller=partial(RemoteController, ip="127.0.0.1", port=6633),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        waitConnected=True,
    )

    pre_stop_log_text = ""
    try:
        disable_ipv6(net)
        net.start()
        src_host, dst_host = net.get(SOURCE_HOST, DEST_HOST)
        src_mac = src_host.MAC()
        dst_mac = dst_host.MAC()

        src_host.cmd(f"ping -c 1 -W 1 {DEST_IP} >/dev/null 2>&1")
        time.sleep(1)

        ping_output = src_host.cmd(f"ping -n -c {PING_COUNT} -i {PING_INTERVAL} {DEST_IP}")
        ping_rows = parse_ping_output(ping_output)
        if len(ping_rows) < PING_COUNT:
            raise RuntimeError(
                f"expected {PING_COUNT} RTT samples for {algorithm}, got {len(ping_rows)}"
            )

        pre_stop_log_text = controller_log_path.read_text(encoding="utf-8", errors="ignore")
    finally:
        net.stop()
        stop_controller(controller_process)

    controller_log_text = pre_stop_log_text or controller_log_path.read_text(
        encoding="utf-8", errors="ignore"
    )

    raw_path = parse_flow_install_log(controller_log_text, src_mac, dst_mac)
    if raw_path is None:
        path_info = parse_path_log(
            controller_log_text,
            expected_src=SOURCE_SWITCH_DPID,
            expected_dst=DEST_SWITCH_DPID,
        )
        if path_info is None:
            raise RuntimeError(f"no usable path entry found in controller log for {algorithm}")
        raw_path = str(path_info["path"])

    raw_path = normalize_path_direction(raw_path, SOURCE_SWITCH_DPID, DEST_SWITCH_DPID)
    path = format_path_labels(raw_path)
    hop_count = max(0, len(parse_path_nodes(raw_path)) - 1)
    total_delay_ms = compute_path_delay(raw_path, delay_weights)

    rows: List[Dict[str, object]] = []
    for idx, ping_row in enumerate(ping_rows, start=1):
        rows.append(
            {
                "algorithm": algorithm,
                "controller": controller_path.name,
                "source_host": SOURCE_HOST,
                "destination_host": DEST_HOST,
                "ping_index": idx,
                "icmp_seq": ping_row["icmp_seq"],
                "warmup": 1 if idx <= WARMUP_DROP else 0,
                "include_in_analysis": 0 if idx <= WARMUP_DROP else 1,
                "rtt_ms": ping_row["rtt_ms"],
                "path": path,
                "path_switches": raw_path,
                "hop_count": hop_count,
                "total_delay_ms": total_delay_ms,
                "raw_ping_line": ping_row["raw_line"],
                "controller_log": str(controller_log_path),
            }
        )

    return ExperimentResult(
        algorithm=algorithm,
        controller=controller_path.name,
        path=path,
        hop_count=hop_count,
        total_delay_ms=total_delay_ms,
        rows=rows,
    )


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
    parser = argparse.ArgumentParser(description="Mesh latency benchmark")
    parser.add_argument(
        "--output",
        default=str(RESULTS_DIR / "mesh_latency.csv"),
        help="Path to the CSV output file",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=DEFAULT_ALGORITHMS,
        choices=DEFAULT_ALGORITHMS,
        help="Algorithms to run",
    )
    args = parser.parse_args()

    setLogLevel("warning")
    output_path = Path(args.output)

    with tempfile.TemporaryDirectory(prefix="mesh_weights_") as temp_dir:
        weights_file = Path(temp_dir) / "mesh_delay_weights.json"
        write_delay_weights(weights_file)
        delay_weights = build_delay_weights()
        all_rows: List[Dict[str, object]] = []
        for algorithm in args.algorithms:
            result = run_single_algorithm(algorithm, delay_weights, weights_file)
            all_rows.extend(result.rows)

        write_csv(all_rows, output_path)

    print(f"Wrote {len(all_rows)} rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
