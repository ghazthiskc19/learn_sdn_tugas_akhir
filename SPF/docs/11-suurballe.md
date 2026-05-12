# 11 - Suurballe and FAST_FAILOVER

Suurballe's algorithm finds two edge-disjoint shortest paths between the same
source and destination. In SDN, this is a natural match for OpenFlow
FAST_FAILOVER groups, which let the dataplane switch to a backup path without
waiting for the controller to react.

---

## Motivation

In ECMP, traffic is load-balanced across equal-cost paths, but both paths can
still be affected by a single link failure. With edge-disjoint paths, the
backup path survives a first-hop link failure.

```
Primary:  s1 - s2 - s4
Backup:   s1 - s3 - s4
```

If the s1->s2 link goes down, traffic should immediately move to s1->s3.

---

## Algorithm Overview (Suurballe)

Suurballe computes two disjoint paths by running Dijkstra twice:

1. Run Dijkstra from src to get the shortest path P1 and distances dist[].
2. Build reduced costs: w'(u,v) = w(u,v) + dist[u] - dist[v].
3. Remove edges on P1 and add their reverse edges with cost 0.
4. Run Dijkstra again to get P2 in the modified graph.
5. Combine edges from P1 and P2, cancel opposite edges, and split into two
   edge-disjoint paths.

The result is two shortest, edge-disjoint paths (if they exist).

---

## OpenFlow FAST_FAILOVER Groups

FAST_FAILOVER groups select the first live bucket by checking a watch port.
The switch does not consult the controller when a watched port fails.
This means FAST_FAILOVER does not load-balance traffic.

```
Group Table Entry:
  Group ID: 9
  Type: FAST_FAILOVER
  Buckets:
    - watch_port=3, action: output(3)  # primary
    - watch_port=4, action: output(4)  # backup
```

When port 3 goes down, the switch instantly uses port 4.

---

## Controller Behavior

The controller:

- Computes two disjoint paths with Suurballe
- Installs unicast flows on transit and egress switches for both paths
- Installs one FAST_FAILOVER group on the ingress switch
- Installs a group-action flow for the ingress match

Scope: ingress-only protection. Failures beyond the first hop are still
handled by topology-change recomputation.

---

## Balanced Failover (Load Balance + Fast Failover)

The balanced failover controller installs two FAST_FAILOVER groups (one per
primary port) and a SELECT group that hashes flows across those groups.
Under normal conditions, traffic is balanced across the two disjoint paths.
If a first-hop port fails, the corresponding FAST_FAILOVER group moves traffic
to the other path.

Run:

```bash
python3 SPF/suurballe_balanced_failover_osken_controller.py --verbose
```

Note: this relies on group chaining support in the switch (OVS supports this).

Verification (balanced failover):

```bash
# In Mininet
h4 iperf3 -s -D
h1 iperf3 -c 10.2.0.4 -P 4 -t 8
dpctl dump-groups -O OpenFlow13
dpctl dump-group-stats -O OpenFlow13

# Failover the primary link
link s1 s2 down
h1 iperf3 -c 10.2.0.4 -P 4 -t 8
dpctl dump-group-stats -O OpenFlow13
```

Expectations:

- The SELECT group should have two buckets (one per FAST_FAILOVER group).
- Both group bucket counters should increase with parallel flows.
- After link down, traffic continues and bucket counters keep rising.

---

## Lab: Observe Fast Failover

```bash
# Terminal 1
python3 SPF/topo-ecmp_lab.py

# Terminal 2
python3 SPF/suurballe_fast_failover_osken_controller.py --verbose
```

In Mininet:

```
mininet> h1 ping h4
mininet> dpctl dump-groups -O OpenFlow13
mininet> link s1 s2 down
mininet> h1 ping h4
```

You should see traffic continue when the primary link drops.

---

## Limitations

- Requires non-negative edge weights
- Only two paths (primary + backup)
- FAST_FAILOVER only protects the ingress first hop
- No load balancing: the primary bucket is always used until failure
- Balanced failover requires group chaining support

---

## See Also

- docs/09-ecmp.md
- docs/10-yen-k-shortest.md
