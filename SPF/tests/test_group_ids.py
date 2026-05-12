"""Tests for algorithms/group_ids.py"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from algorithms.group_ids import alloc_group_id_triple


class TestGroupIdTriple:
    def test_deterministic_for_same_seed(self):
        t1 = alloc_group_id_triple("a->b", space=97)
        t2 = alloc_group_id_triple("a->b", space=97)
        assert t1 == t2

    def test_avoids_used_ids(self):
        base = alloc_group_id_triple("a->b", space=97)
        used = set(base)
        nxt = alloc_group_id_triple("a->b", used_ids=used, space=97)
        assert not any(gid in used for gid in nxt)
        assert base != nxt

    def test_stays_within_space(self):
        triple = alloc_group_id_triple("x->y", space=9)
        assert all(1 <= gid <= 9 for gid in triple)
        assert triple[0] < triple[1] < triple[2]

    def test_handles_dense_used_set(self):
        used = {1, 2, 3, 4, 5, 6}
        triple = alloc_group_id_triple("seed", used_ids=used, space=9)
        assert not any(gid in used for gid in triple)
        assert triple == (7, 8, 9)
