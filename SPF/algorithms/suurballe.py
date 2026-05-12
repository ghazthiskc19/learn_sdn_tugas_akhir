"""Suurballe's algorithm for two edge-disjoint shortest paths.

Finds up to two edge-disjoint shortest paths between src and dst.
Works with non-negative edge weights and returns node paths.

Complexity: O((V + E) log V) for two Dijkstra runs
Use when:    You want a primary path and a disjoint backup for failover.
"""

import heapq
from collections import defaultdict

INF = float("inf")


def _iter_neighbors(adjacency, u):
    for item in adjacency.get(u, []):
        if isinstance(item, (tuple, list)):
            if not item:
                continue
            yield item[0]
        else:
            yield item


def _edge_cost(weights, u, v):
    if weights and (u, v) in weights:
        return weights[(u, v)]
    return 1


def _dijkstra(adjacency, src, weights):
    distance = {}
    previous = {}

    for u in adjacency:
        distance.setdefault(u, INF)
        previous.setdefault(u, None)
        for v in _iter_neighbors(adjacency, u):
            distance.setdefault(v, INF)
            previous.setdefault(v, None)

    if src not in distance:
        return distance, previous

    distance[src] = 0
    heap = [(0, src)]

    while heap:
        d, u = heapq.heappop(heap)
        if d != distance.get(u, INF):
            continue
        for v in _iter_neighbors(adjacency, u):
            cost = _edge_cost(weights, u, v)
            alt = d + cost
            if alt < distance.get(v, INF):
                distance[v] = alt
                previous[v] = u
                heapq.heappush(heap, (alt, v))

    return distance, previous


def _reconstruct(previous, src, dst):
    if src == dst:
        return [src]
    if dst not in previous or previous.get(dst) is None:
        return None
    path = [dst]
    current = previous.get(dst)
    while current is not None:
        path.append(current)
        if current == src:
            break
        current = previous.get(current)
    if not path or path[-1] != src:
        return None
    return list(reversed(path))


def _path_edges(path):
    return [(u, v) for u, v in zip(path[:-1], path[1:])]


def _add_edge(adj, weights, u, v, cost):
    adj[u].add(v)
    existing = weights.get((u, v))
    if existing is None or cost < existing:
        weights[(u, v)] = cost


def _find_path(edges, src, dst):
    graph = defaultdict(list)
    for u, v in edges:
        graph[u].append(v)
    for u in graph:
        graph[u].sort()

    def dfs(node, path, seen):
        if node == dst:
            return path
        for v in graph.get(node, []):
            if v in seen:
                continue
            edge = (node, v)
            if edge not in edges:
                continue
            seen.add(v)
            result = dfs(v, path + [v], seen)
            if result:
                return result
            seen.remove(v)
        return None

    return dfs(src, [src], {src})


def _extract_paths(edges, src, dst):
    remaining = set(edges)
    paths = []
    for _ in range(2):
        path = _find_path(remaining, src, dst)
        if not path:
            break
        paths.append(path)
        for edge in _path_edges(path):
            remaining.discard(edge)
        if not remaining:
            break
    return paths


def _path_cost(path, weights):
    total = 0
    for u, v in _path_edges(path):
        total += _edge_cost(weights, u, v)
    return total


def _undirected_edge_set(path):
    return {tuple(sorted((u, v))) for u, v in _path_edges(path)}


def _edge_disjoint(p1, p2):
    return _undirected_edge_set(p1).isdisjoint(_undirected_edge_set(p2))


def suurballe_edge_disjoint(adjacency, src, dst, weights=None):
    """Return up to two edge-disjoint shortest paths from src to dst.

    Args:
        adjacency: dict {node: [(neighbor, out_port), ...]}
        src:       source node
        dst:       destination node
        weights:   optional dict {(u, v): cost} (non-negative)

    Returns:
        List of node paths: [[src, ..., dst], ...]
        If no path exists, returns []. If only one path exists, returns [path].
    """
    if src == dst:
        return [[src]]

    dist, prev = _dijkstra(adjacency, src, weights)
    if dist.get(dst, INF) == INF:
        return []

    path1 = _reconstruct(prev, src, dst)
    if not path1:
        return []

    p1_edges = set(_path_edges(path1))

    # Build reduced-cost graph with edges on path1 reversed at zero cost.
    adj2 = defaultdict(set)
    w2 = {}
    for u in adjacency:
        for v in _iter_neighbors(adjacency, u):
            if dist.get(u, INF) == INF or dist.get(v, INF) == INF:
                continue
            if (u, v) in p1_edges:
                continue
            cost = _edge_cost(weights, u, v)
            reduced = cost + dist[u] - dist[v]
            if reduced < 0:
                reduced = 0
            _add_edge(adj2, w2, u, v, reduced)

    for u, v in p1_edges:
        _add_edge(adj2, w2, v, u, 0)

    dist2, prev2 = _dijkstra(adj2, src, w2)
    if dist2.get(dst, INF) == INF:
        return [path1]

    path2 = _reconstruct(prev2, src, dst)
    if not path2:
        return [path1]

    combined = set(p1_edges)
    combined.update(_path_edges(path2))

    # Cancel opposite directed edges to form two disjoint paths.
    for u, v in list(combined):
        if (v, u) in combined:
            combined.discard((u, v))
            combined.discard((v, u))

    paths = _extract_paths(combined, src, dst)
    if not paths:
        return [path1]

    paths = sorted(paths, key=lambda p: _path_cost(p, weights))
    if len(paths) >= 2 and not _edge_disjoint(paths[0], paths[1]):
        return [paths[0]]

    return paths[:2]
