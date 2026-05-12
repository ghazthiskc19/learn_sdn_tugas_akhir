"""Helpers to run common network measurements via Mininet host.cmd().

This module provides small wrappers for ping, traceroute and iperf3
invocations executed on Mininet host objects.
"""
import re
import time


def parse_ping(output: str):
    """Parse `ping -c N` output and return (sent, received, loss_percent, avg_ms).
    Returns avg_ms as float or None if unavailable.
    """
    # Example summary line: rtt min/avg/max/mdev = 0.025/0.025/0.025/0.000 ms
    sent = received = loss = None
    m = re.search(r"(\d+) packets transmitted, (\d+) received, (\d+)% packet loss", output)
    if m:
        sent = int(m.group(1))
        received = int(m.group(2))
        loss = int(m.group(3))
    rtt = None
    m2 = re.search(r"rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/", output)
    if m2:
        try:
            rtt = float(m2.group(1))
        except ValueError:
            rtt = None
    return sent, received, loss, rtt


def parse_iperf3(output: str):
    """Parse simple iperf3 client output, return throughput Mbps as float if found."""
    # Look for a line like: [ ID]   0.00-10.00  sec  1.10 GBytes  943 Mbits/sec
    m = re.search(r"sec\s+[\d\.]+\s+[A-Za-z]+\s+[\d\.]+\s+([\d\.]+)\s+Mbits/sec", output)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    # try alternate: Kbits/sec or Gbits/sec
    m2 = re.search(r"sec\s+[\d\.]+\s+[A-Za-z]+\s+[\d\.]+\s+([\d\.]+)\s+Gbits/sec", output)
    if m2:
        try:
            return float(m2.group(1)) * 1000.0
        except ValueError:
            return None
    return None


def parse_traceroute(output: str):
    """Return hop count from traceroute output (number of non-empty hops)."""
    lines = [l for l in output.splitlines() if l.strip()]
    # ignore header line
    if not lines:
        return 0
    # Count lines that start with a hop number
    hops = 0
    for ln in lines:
        if re.match(r"^\s*\d+\s+", ln):
            hops += 1
    return hops


def find_path_computed_timestamps(controller_log_path, src_dpid, dst_dpid):
    """Parse controller log for [PATH-COMPUTED] entries matching src->dst.
    Returns list of (timestamp_str, time_unix_if_available) tuples.
    """
    results = []
    try:
        with open(controller_log_path, 'r') as f:
            for line in f:
                # Look for: [PATH-COMPUTED] s1->s12: ...
                if '[PATH-COMPUTED]' in line and f's{src_dpid}->' in line and f'-s{dst_dpid}' in line:
                    results.append((line, time.time()))  # timestamp is log line time (approx)
    except Exception:
        pass
    return results

