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
        host_a1 = self.addHost("HostA1", ip="10.0.0.1/24")
        host_a2 = self.addHost("HostA2", ip="10.0.0.2/24")
        host_b1 = self.addHost("HostB1", ip="10.0.0.3/24")
        host_b2 = self.addHost("HostB2", ip="10.0.0.4/24")
        host_d1 = self.addHost("HostD1", ip="10.0.0.5/24")
        host_d2 = self.addHost("HostD2", ip="10.0.0.6/24")
        host_e1 = self.addHost("HostE1", ip="10.0.0.7/24")
        host_e2 = self.addHost("HostE2", ip="10.0.0.8/24")

        info("*** Adding switches\n")
        switch_a = self.addSwitch("SwitchA")
        switch_b = self.addSwitch("SwitchB")
        switch_c = self.addSwitch("SwitchC")
        switch_d = self.addSwitch("SwitchD")
        switch_e = self.addSwitch("SwitchE")
        switch_f = self.addSwitch("SwitchF")

        info("*** Adding host links\n")
        self.addLink(host_a1, switch_a, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_a2, switch_a, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_b1, switch_b, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_b2, switch_b, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_d1, switch_d, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_d2, switch_d, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_e1, switch_e, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(host_e2, switch_e, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)

        info("*** Adding switch links\n")
        # Full mesh: every switch connects to every other switch.
        self.addLink(switch_a, switch_b, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_c, port1=4, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_d, port1=5, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_e, port1=6, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_a, switch_f, port1=7, port2=3, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_b, switch_c, port1=4, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_d, port1=5, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_e, port1=6, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_b, switch_f, port1=7, port2=4, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_c, switch_d, port1=5, port2=5, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_c, switch_e, port1=6, port2=5, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_c, switch_f, port1=7, port2=5, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_d, switch_e, port1=6, port2=6, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(switch_d, switch_f, port1=7, port2=6, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(switch_e, switch_f, port1=7, port2=7, bw=500, delay='1ms', use_hfsc=True)


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