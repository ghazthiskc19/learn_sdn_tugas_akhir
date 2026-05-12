"""Group ID allocation helpers for OpenFlow group chaining.

Provides deterministic, collision-avoiding group ID triples for SELECT +
FAST_FAILOVER group stacks.
"""

import hashlib


def _hash_seed(seed):
    if isinstance(seed, str):
        seed = seed.encode()
    if not isinstance(seed, (bytes, bytearray)):
        seed = str(seed).encode()
    return int(hashlib.md5(seed).hexdigest()[:8], 16)


def alloc_group_id_triple(seed, used_ids=None, space=0x7FFFFFFF):
    """Allocate a collision-free group-id triple within a bounded space.

    Returns (select_gid, ff_gid_a, ff_gid_b) where the three IDs are contiguous.
    """
    used = set(used_ids or set())
    if space < 3:
        return 1, 2, 3

    max_base = space - 2
    if max_base < 1:
        return 1, 2, 3

    candidate = _hash_seed(seed) & space
    candidate = ((candidate - 1) % max_base) + 1

    while any(gid in used for gid in (candidate, candidate + 1, candidate + 2)):
        candidate = (candidate % max_base) + 1

    return candidate, candidate + 1, candidate + 2
