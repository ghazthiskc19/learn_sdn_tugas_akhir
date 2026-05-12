"""Tests for algorithms/suurballe.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithms.suurballe import suurballe_edge_disjoint


def _undirected_edges(path):
    return {tuple(sorted((u, v))) for u, v in zip(path[:-1], path[1:])}


def _is_simple(path):
    return len(path) == len(set(path))


def _path_cost(path, weights):
    total = 0
    for u, v in zip(path[:-1], path[1:]):
        total += weights.get((u, v), 1)
    return total


class TestSuurballeBasic:
    def test_diamond_two_paths(self, diamond):
        paths = suurballe_edge_disjoint(diamond.adj, 1, 4)
        assert len(paths) == 2
        for p in paths:
            assert p[0] == 1
            assert p[-1] == 4
            assert _is_simple(p)
        assert _undirected_edges(paths[0]).isdisjoint(_undirected_edges(paths[1]))

    def test_ring4_two_paths(self, ring4):
        paths = suurballe_edge_disjoint(ring4.adj, 1, 3)
        assert len(paths) == 2
        assert _undirected_edges(paths[0]).isdisjoint(_undirected_edges(paths[1]))

    def test_linear_only_one_path(self, linear3):
        paths = suurballe_edge_disjoint(linear3.adj, 1, 3)
        assert len(paths) == 1
        assert paths[0] == [1, 2, 3]

    def test_unreachable_returns_empty(self, disconnected):
        paths = suurballe_edge_disjoint(disconnected.adj, 1, 3)
        assert paths == []

    def test_weighted_prefers_cheapest_primary(self):
        adj = {
            1: [(2, 12), (3, 13)],
            2: [(1, 21), (4, 24)],
            3: [(1, 31), (4, 34)],
            4: [(2, 42), (3, 43)],
        }
        weights = {
            (1, 2): 10, (2, 1): 10,
            (2, 4): 10, (4, 2): 10,
            (1, 3): 1,  (3, 1): 1,
            (3, 4): 1,  (4, 3): 1,
        }
        paths = suurballe_edge_disjoint(adj, 1, 4, weights=weights)
        assert len(paths) == 2
        costs = [_path_cost(p, weights) for p in paths]
        assert costs[0] <= costs[1]
        assert 3 in paths[0]
