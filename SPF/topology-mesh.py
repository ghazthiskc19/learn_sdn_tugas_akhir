#!/usr/bin/env python3

from functools import partial

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.cli import CLI


class MeshTopo(Topo):
    def addSwitch(self, name, **opts):
        kwargs = {"protocols": "OpenFlow13"}
        kwargs.update(opts)
        if "dpid" not in kwargs:
            kwargs["dpid"] = f"{self._next_dpid:016x}"
            self._next_dpid += 1
        return super(MeshTopo, self).addSwitch(name, **kwargs)

    def __init__(self):
        Topo.__init__(self)
        self._next_dpid = 1

        info("*** Adding hosts\n")
        host_a = self.addHost("HostA", ip="10.0.0.1/24")
        host_b = self.addHost("HostB", ip="10.0.0.2/24")
        host_c = self.addHost("HostC", ip="10.0.0.3/24")
        host_d = self.addHost("HostD", ip="10.0.0.4/24")

        info("*** Adding switches\n")
        switch_a = self.addSwitch("SwitchA")
        switch_b = self.addSwitch("SwitchB")
        switch_c = self.addSwitch("SwitchC")
        switch_d = self.addSwitch("SwitchD")

        info("*** Adding host links\n")
        # Setiap switch hanya terhubung ke 1 host. Port diatur ulang ke port universal.
        self.addLink(host_a, switch_a, port1=1, port2=1, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(host_b, switch_b, port1=1, port2=1, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(host_c, switch_c, port1=1, port2=1, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(host_d, switch_d, port1=1, port2=1, bw=500, delay='1ms', use_hfsc=True)

        info("*** Adding switch links\n")
        # Full mesh untuk 4 switch yang tersisa (Semua menggunakan bw=500 dan delay='1ms')
        self.addLink(switch_a, switch_b, port1=2, port2=2, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_d, port1=3, port2=2, bw=50, delay='50ms', use_hfsc=True)
        self.addLink(switch_a, switch_c, port1=4, port2=2, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_b, switch_d, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_c, port1=4, port2=3, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_d, switch_c, port1=4, port2=4, bw=500, delay='1ms', use_hfsc=True)


def run():
    topo = MeshTopo()
    net = Mininet(
        topo=topo,
        controller=partial(RemoteController, ip="127.0.0.1", port=6633),
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
        waitConnected=True,
    )
    info("\n*** Disabling IPv6\n")
    for host in net.hosts:
        info(f"disable ipv6 in {host}\n")
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")

    for sw in net.switches:
        info(f"disable ipv6 in {sw}\n")
        sw.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")

    net.start()

    info("*** Dumping host connections\n")
    dumpNodeConnections(net.hosts)
    info("\n*** Network is running. Type 'pingall' to test full connectivity.\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()