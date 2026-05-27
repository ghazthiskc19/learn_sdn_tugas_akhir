#!/usr/bin/env python3
"""Hierarchy convergence benchmark with phantom graph injection."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import RemoteController

ROOT_DIR = Path(__file__).resolve().parents[3]
SPF_DIR = ROOT_DIR / "SPF"
RESULTS_DIR = ROOT_DIR / "scripts" / "experiments" / "results" / "hierarchy"
TOPOLOGY_FILE = SPF_DIR / "topology-hierarchy.py"

SOURCE_HOST = "Host1"
DEST_HOST = "Host4"
DEST_IP = "10.0.0.4"
SOURCE_SWITCH_DPID = 10
DEST_SWITCH_DPID = 13

TOPOLOGY_FLAP_LINK = ("Core1", "Core3")
OF_PORT = 6633

DEFAULT_ALGORITHMS = ["bfs", "astar", "bellman-ford", "dijkstra"]
ALGORITHM_CONTROLLERS = {
    "bfs": SPF_DIR / "bfs_osken_controller.py",
    "astar": SPF_DIR / "astar_osken_controller.py",
    "bellman-ford": SPF_DIR / "bellman_ford_osken_controller.py",
    "dijkstra": SPF_DIR / "dijkstra_osken_controller.py",
}

PHANTOM_NODE_COUNT = 500
PHANTOM_EDGE_COUNT = 2000
PHANTOM_WEIGHT_MIN = 1
PHANTOM_WEIGHT_MAX = 100
PHANTOM_SEED = 42
PHANTOM_SOURCE = 0
PHANTOM_TARGET = PHANTOM_NODE_COUNT - 1

PATH_RE = re.compile(r"\[PATH-COMPUTED\]\s+(?:\S+\s+)?s(\d+)(?:->|→)s(\d+):\s+(\d+)\s+hop\(s\)\s+path=(.+)")
CONVERGENCE_START_RE = re.compile(r"\[CONVERGENCE-START\]\s+id=(\d+)\s+t1=([0-9.]+)")
CONVERGENCE_FLOWMOD_RE = re.compile(r"\[CONVERGENCE-FLOWMOD\]\s+id=(\d+)\s+t2=([0-9.]+)")
# FIX: Regex ini sekarang bisa menangkap tag -UNCHANGED jika path ternyata sama
CONVERGENCE_END_RE = re.compile(r"\[CONVERGENCE-END(?:-UNCHANGED)?\]\s+id=(\d+)\s+convergence_ms=([0-9.]+)")

@dataclass
class ExperimentRow:
    scenario_type: str
    algorithm: str
    controller: str
    payload: Dict[str, object]

def load_topology_class():
    spec = importlib.util.spec_from_file_location("topology_hierarchy", TOPOLOGY_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HierarchyTopo

def build_delay_weights() -> Dict[str, Dict[str, float]]:
    links = {
        "1:2": {"delay_ms": 50.0},
        "1:3": {"delay_ms": 0.5},
        "2:3": {"delay_ms": 0.5},
        "3:1": {"delay_ms": 0.5},
        "4:5": {"delay_ms": 1.0},
        "4:10": {"delay_ms": 1.0},
        "4:11": {"delay_ms": 1.0},
        "4:1": {"delay_ms": 0.5},
        "5:10": {"delay_ms": 1.0},
        "5:11": {"delay_ms": 1.0},
        "5:1": {"delay_ms": 0.5},
        "6:7": {"delay_ms": 1.0},
        "6:12": {"delay_ms": 1.0},
        "6:13": {"delay_ms": 1.0},
        "6:2": {"delay_ms": 0.5},
        "7:12": {"delay_ms": 1.0},
        "7:13": {"delay_ms": 1.0},
        "7:2": {"delay_ms": 0.5},
        "10:1": {"delay_ms": 2.0},
        "11:1": {"delay_ms": 2.0},
        "12:1": {"delay_ms": 2.0},
        "13:1": {"delay_ms": 2.0},
    }
    return {"links": links}

def build_hierarchy_route_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from([1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13])
    edges = [
        (1, 2, 50.0), (1, 3, 0.5), (2, 3, 0.5),
        (4, 5, 1.0), (4, 10, 1.0), (4, 11, 1.0), (4, 1, 0.5),
        (5, 10, 1.0), (5, 11, 1.0), (5, 1, 0.5),
        (6, 7, 1.0), (6, 12, 1.0), (6, 13, 1.0), (6, 2, 0.5),
        (7, 12, 1.0), (7, 13, 1.0), (7, 2, 0.5),
    ]
    for left, right, delay_ms in edges:
        if {left, right} == {1, 3}: continue
        graph.add_edge(left, right, delay_ms=delay_ms)
    return graph

def compute_fallback_route(algorithm: str) -> Optional[str]:
    graph = build_hierarchy_route_graph()
    try:
        if algorithm == "bfs":
            nodes = nx.shortest_path(graph, SOURCE_SWITCH_DPID, DEST_SWITCH_DPID)
        else:
            nodes = nx.shortest_path(graph, SOURCE_SWITCH_DPID, DEST_SWITCH_DPID, weight="delay_ms")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    return " -> ".join(f"s{node}" for node in nodes)

def write_delay_weights(path: Path) -> None:
    path.write_text(json.dumps(build_delay_weights(), indent=2, sort_keys=True) + "\n")

def wait_for_controller(port: int = OF_PORT, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"controller did not open 127.0.0.1:{port} within {timeout}s")

def mininet_cleanup() -> None:
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def disable_ipv6(net: Mininet) -> None:
    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")
    for switch in net.switches:
        switch.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1")

def start_controller(algorithm: str, controller_path: Path, weights_file: Path, ofp_port: int) -> tuple[subprocess.Popen, Path]:
    temp_dir = Path(tempfile.mkdtemp(prefix=f"hierarchy_conv_{algorithm}_"))
    log_path = temp_dir / "controller.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if algorithm != "bfs":
        env["SPF_WEIGHTS_FILE"] = str(weights_file)
        env["SPF_WEIGHT_FIELD"] = "delay_ms"

    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(controller_path), "--verbose", "--ofp-tcp-listen-port", str(ofp_port)],
        stdout=log_handle, stderr=subprocess.STDOUT, env=env,
    )
    process._log_handle = log_handle
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

def parse_path_log(log_text: str, expected_src: Optional[int] = None, expected_dst: Optional[int] = None) -> Optional[str]:
    matches = PATH_RE.findall(log_text)
    if not matches: return None
    selected = None
    for src, dst, _hops, path in matches:
        if expected_src is not None and expected_dst is not None and int(src) == expected_src and int(dst) == expected_dst:
            selected = path
            break
    if selected is None: selected = matches[-1][3]
    return selected.strip()

def parse_convergence(log_text: str) -> Dict[str, object]:
    start = CONVERGENCE_START_RE.search(log_text)
    flowmod = CONVERGENCE_FLOWMOD_RE.search(log_text)
    end = CONVERGENCE_END_RE.search(log_text)
    result = {
        "convergence_id": None, "convergence_t1": None, 
        "convergence_t2": None, "convergence_ms": None,
    }
    if start:
        result["convergence_id"] = int(start.group(1))
        result["convergence_t1"] = float(start.group(2))
    if flowmod:
        result["convergence_t2"] = float(flowmod.group(2))
    if end:
        result["convergence_id"] = int(end.group(1))
        result["convergence_ms"] = float(end.group(2))
    if result["convergence_ms"] is None and result["convergence_t1"] is not None and result["convergence_t2"] is not None:
        result["convergence_ms"] = (float(result["convergence_t2"]) - float(result["convergence_t1"])) * 1000.0
    return result

def format_path(path: str) -> str:
    nodes = [int(node) for node in re.findall(r"s(\d+)", path)]
    return " -> ".join(f"s{node}" for node in nodes)

def path_hops(path: str) -> int:
    return max(0, len(re.findall(r"s(\d+)", path)) - 1)

def run_scenario_a(algorithm: str, weights_file: Path, ofp_port: int, verbose: bool) -> ExperimentRow:
    controller_path = ALGORITHM_CONTROLLERS[algorithm]
    if verbose: print(f"[SCENARIO A] start algorithm = {algorithm}")
    controller_process, controller_log_path = start_controller(algorithm, controller_path, weights_file, ofp_port)
    wait_for_controller(port=ofp_port)

    topology_cls = load_topology_class()
    topo = topology_cls()
    net = Mininet(
        topo=topo, controller=partial(RemoteController, ip="127.0.0.1", port=ofp_port),
        link=TCLink, autoSetMacs=True, autoStaticArp=True, waitConnected=True,
    )

    ping_proc = None
    try:
        disable_ipv6(net)
        net.start()
        
        # FIX: Wajib tunggu OSKen install rule Table-Miss
        if verbose: print("[SCENARIO A] Menunggu OpenFlow handshake selesai (5s)...")
        time.sleep(5.0)

        src_host, _dst_host = net.get(SOURCE_HOST, DEST_HOST)

        if verbose: print(f"[SCENARIO A] Memaksa ARP dan host learning (1x ping)...")
        net.ping([src_host, net.get(DEST_HOST)])

        time.sleep(5.0)

        if verbose: print(f"[SCENARIO A] Memulai background traffic...")
        ping_proc = src_host.popen(f"ping -i 0.1 {DEST_IP} > /dev/null 2>&1")
        time.sleep(2.0)

        flap_src, flap_dst = TOPOLOGY_FLAP_LINK
        if verbose: print(f"[SCENARIO A] Flapping link {flap_src}<->{flap_dst}")
        flap_started_at = time.perf_counter()
        net.configLinkStatus(flap_src, flap_dst, "down")

        # FIX: Wajib tunggu LLDP timeout dari sisi controller (10s)
        if verbose: print("[SCENARIO A] Menunggu LLDP timeout dari Ryu/OSKen (10s)...")
        time.sleep(10.0)

        controller_log_text = controller_log_path.read_text(encoding="utf-8", errors="ignore")
        convergence = parse_convergence(controller_log_text)
        if convergence.get("convergence_ms") is None:
            convergence["convergence_ms"] = (time.perf_counter() - flap_started_at) * 1000.0
            convergence["convergence_source"] = "fallback_elapsed"
        else:
            convergence["convergence_source"] = "controller_log"
            
        path_info = parse_path_log(controller_log_text, expected_src=SOURCE_SWITCH_DPID, expected_dst=DEST_SWITCH_DPID)
        if path_info is not None:
            raw_path = path_info
            path_source = "controller_log"
        else:
            raw_path = compute_fallback_route(algorithm) or ""
            path_source = "topology_fallback" if raw_path else "unavailable"

        payload = {
            "scenario_type": "scenario_a",
            "topology_event": f"{flap_src}<->{flap_dst}_down",
            "path": format_path(raw_path), "hop_count": path_hops(raw_path),
            "path_source": path_source, "controller_log": str(controller_log_path),
        }
        payload.update(convergence)
        return ExperimentRow(scenario_type="scenario_a", algorithm=algorithm, controller=controller_path.name, payload=payload)
    finally:
        if ping_proc is not None:
            ping_proc.terminate()
            try: ping_proc.wait(timeout=2)
            except subprocess.TimeoutExpired: ping_proc.kill()
        net.stop()
        stop_controller(controller_process)

# (Skenario B dibiarkan persis sama karena sudah aman dari dulu)
def _build_phantom_graph() -> Tuple[Dict[int, List[Tuple[int, int]]], Dict[Tuple[int, int], int], List[Tuple[int, int, int]]]:
    rng = random.Random(PHANTOM_SEED)
    graph = nx.Graph()
    graph.add_nodes_from(range(PHANTOM_NODE_COUNT))
    for node in range(PHANTOM_NODE_COUNT - 1):
        graph.add_edge(node, node + 1, cost=rng.randint(PHANTOM_WEIGHT_MIN, PHANTOM_WEIGHT_MAX))
    while graph.number_of_edges() < PHANTOM_EDGE_COUNT:
        u, v = rng.randrange(PHANTOM_NODE_COUNT), rng.randrange(PHANTOM_NODE_COUNT)
        if u == v or graph.has_edge(u, v): continue
        graph.add_edge(u, v, cost=rng.randint(PHANTOM_WEIGHT_MIN, PHANTOM_WEIGHT_MAX))

    adjacency: Dict[int, List[Tuple[int, int]]] = {node: [] for node in graph.nodes}
    weights: Dict[Tuple[int, int], int] = {}
    edges: List[Tuple[int, int, int]] = []
    for u, v, data in graph.edges(data=True):
        cost = int(data["cost"])
        adjacency[u].append((v, len(adjacency[u]) + 1))
        adjacency[v].append((u, len(adjacency[v]) + 1))
        weights[(u, v)] = weights[(v, u)] = cost
        edges.append((u, v, cost))
    return adjacency, weights, edges

def _reverse_hop_heuristic(adjacency: Dict[int, List[Tuple[int, int]]], dst: int) -> Dict[int, int]:
    hops = {dst: 0}
    queue = deque([dst])
    while queue:
        u = queue.popleft()
        for v, _ in adjacency.get(u, []):
            if v not in hops:
                hops[v] = hops[u] + 1
                queue.append(v)
    return hops

def _reconstruct_path(previous: Dict[int, Optional[int]], src: int, dst: int) -> Optional[List[int]]:
    if src == dst: return [src]
    if dst not in previous or previous[dst] is None: return None
    path, current = [dst], previous[dst]
    while current is not None:
        path.append(current)
        if current == src: break
        current = previous.get(current)
    if not path or path[-1] != src: return None
    return list(reversed(path))

def _phantom_bfs(adjacency, src, dst):
    distance = {node: float("inf") for node in adjacency}
    previous = {node: None for node in adjacency}
    visited, queue, distance[src], queue_pops = set(), deque([src]), 0, 0
    while queue:
        u = queue.popleft()
        queue_pops += 1
        if u in visited: continue
        visited.add(u)
        if u == dst: break
        for v, _ in adjacency.get(u, []):
            if distance[v] == float("inf"):
                distance[v], previous[v] = distance[u] + 1, u
                queue.append(v)
    return distance, previous, {"nodes_visited": len(visited), "queue_pops": queue_pops, "heap_pops": 0, "relaxations": 0}

def _phantom_dijkstra(adjacency, weights, src, dst):
    import heapq
    distance, previous = {n: float("inf") for n in adjacency}, {n: None for n in adjacency}
    visited, heap, distance[src], heap_pops, relaxations = set(), [(0, src)], 0, 0, 0
    while heap:
        current_distance, u = heapq.heappop(heap)
        heap_pops += 1
        if u in visited: continue
        visited.add(u)
        if u == dst: break
        for v, _ in adjacency.get(u, []):
            alt = current_distance + weights[(u, v)]
            if alt < distance[v]:
                distance[v], previous[v] = alt, u
                relaxations += 1
                heapq.heappush(heap, (alt, v))
    return distance, previous, {"nodes_visited": len(visited), "queue_pops": 0, "heap_pops": heap_pops, "relaxations": relaxations}

def _phantom_astar(adjacency, weights, src, dst):
    import heapq
    heuristic = _reverse_hop_heuristic(adjacency, dst)
    distance, previous = {n: float("inf") for n in adjacency}, {n: None for n in adjacency}
    closed, heap, distance[src], heap_pops, relaxations = set(), [(heuristic.get(src, float("inf")), 0, src)], 0, 0, 0
    while heap:
        _f, current_distance, u = heapq.heappop(heap)
        heap_pops += 1
        if u in closed: continue
        closed.add(u)
        if u == dst: break
        for v, _ in adjacency.get(u, []):
            tentative = current_distance + weights[(u, v)]
            if tentative < distance[v]:
                distance[v], previous[v] = tentative, u
                relaxations += 1
                if heuristic.get(v, float("inf")) < float("inf"):
                    heapq.heappush(heap, (tentative + heuristic[v], tentative, v))
    return distance, previous, {"nodes_visited": len(closed), "queue_pops": 0, "heap_pops": heap_pops, "relaxations": relaxations}

def _phantom_bellman_ford(adjacency, weights, src, dst):
    vertices = list(adjacency.keys())
    distance, previous = {n: float("inf") for n in vertices}, {n: None for n in vertices}
    distance[src], relaxations = 0, 0
    edges = [(u, v, weights[(u, v)]) for u in adjacency for v, _ in adjacency[u]]
    for _ in range(len(vertices) - 1):
        updated = False
        for u, v, cost in edges:
            if distance[u] == float("inf"): continue
            alt = distance[u] + cost
            if alt < distance[v]:
                distance[v], previous[v] = alt, u
                relaxations += 1
                updated = True
        if not updated: break
    return distance, previous, {"nodes_visited": len({n for n, v in distance.items() if v < float("inf")}), "queue_pops": 0, "heap_pops": 0, "relaxations": relaxations}

def run_phantom_algorithm(algorithm: str) -> ExperimentRow:
    adjacency, weights, edges = _build_phantom_graph()
    start = time.perf_counter()
    if algorithm == "bfs": _, previous, metrics = _phantom_bfs(adjacency, PHANTOM_SOURCE, PHANTOM_TARGET)
    elif algorithm == "dijkstra": _, previous, metrics = _phantom_dijkstra(adjacency, weights, PHANTOM_SOURCE, PHANTOM_TARGET)
    elif algorithm == "astar": _, previous, metrics = _phantom_astar(adjacency, weights, PHANTOM_SOURCE, PHANTOM_TARGET)
    elif algorithm == "bellman-ford": _, previous, metrics = _phantom_bellman_ford(adjacency, weights, PHANTOM_SOURCE, PHANTOM_TARGET)
    end = time.perf_counter()
    path_nodes = _reconstruct_path(previous, PHANTOM_SOURCE, PHANTOM_TARGET)
    payload = {
        "scenario_type": "scenario_b", "phantom_seed": PHANTOM_SEED,
        "phantom_nodes": PHANTOM_NODE_COUNT, "phantom_edges": len(edges),
        "source_node": PHANTOM_SOURCE, "destination_node": PHANTOM_TARGET,
        "path": " -> ".join(f"s{n}" for n in path_nodes) if path_nodes else "",
        "hop_count": max(0, len(path_nodes) - 1) if path_nodes else 0,
        "computation_time_us": (end - start) * 1_000_000.0,
        **metrics
    }
    return ExperimentRow(scenario_type="scenario_b", algorithm=algorithm, controller="phantom_graph", payload=payload)

def write_csv(rows: Iterable[Dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fieldnames = [
        "scenario_type", "algorithm", "controller", "topology_event",
        "convergence_id", "convergence_t1", "convergence_t2", "convergence_ms",
        "path", "hop_count", "controller_log", "phantom_seed",
        "phantom_nodes", "phantom_edges", "source_node", "destination_node",
        "computation_time_us", "nodes_visited", "queue_pops", "heap_pops", "relaxations"
    ]
    for row in rows:
        for key in row.keys():
            if key not in fieldnames: fieldnames.append(key)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def run_algorithm_pair(algorithm: str, weights_file: Path, ofp_port: int, verbose: bool) -> List[Dict[str, object]]:
    scenario_a = run_scenario_a(algorithm, weights_file, ofp_port, verbose)
    mininet_cleanup()
    time.sleep(3.0)
    scenario_b = run_phantom_algorithm(algorithm)
    return [
        {**scenario_a.payload, "algorithm": scenario_a.algorithm, "controller": scenario_a.controller},
        {**scenario_b.payload, "algorithm": scenario_b.algorithm, "controller": scenario_b.controller},
    ]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(RESULTS_DIR / "hierarchy_convergence_2.csv"))
    parser.add_argument("--algorithms", nargs="+", default=DEFAULT_ALGORITHMS, choices=DEFAULT_ALGORITHMS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    setLogLevel("warning")

    with tempfile.TemporaryDirectory(prefix="hierarchy_conv_weights_") as temp_dir:
        weights_file = Path(temp_dir) / "hierarchy_delay_weights.json"
        write_delay_weights(weights_file)
        all_rows = []
        for algorithm in args.algorithms:
            mininet_cleanup()
            all_rows.extend(run_algorithm_pair(algorithm, weights_file, OF_PORT, not args.quiet))
        write_csv(all_rows, Path(args.output))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())