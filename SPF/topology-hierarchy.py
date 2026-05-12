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
        return super(MeshTopo, self).addSwitch(name, **kwargs)

    def __init__(self):
        Topo.__init__(self)

        info("*** Adding hosts\n")
        HostA11 = self.addHost("Host1", ip="10.0.0.1/24")
        HostA12 = self.addHost("Host2", ip="10.0.0.2/24")
        HostA21 = self.addHost("Host3", ip="10.0.0.3/24")
        HostA22 = self.addHost("Host4", ip="10.0.0.4/24")

        HostB11 = self.addHost("Host5", ip="10.0.0.5/24")
        HostB12 = self.addHost("Host6", ip="10.0.0.6/24")
        HostB21 = self.addHost("Host7", ip="10.0.0.7/24")
        HostB22 = self.addHost("Host8", ip="10.0.0.8/24")

        HostC11 = self.addHost("Host9", ip="10.0.0.9/24")
        HostC12 = self.addHost("Host10", ip="10.0.0.10/24")
        HostC21 = self.addHost("Host11", ip="10.0.0.11/24")
        HostC22 = self.addHost("Host12", ip="10.0.0.12/24")

        info("*** Adding switches\n")
        CoreA = self.addSwitch("Core1", dpid="0000000000000001")
        CoreB = self.addSwitch("Core2", dpid="0000000000000002")
        coreC = self.addSwitch("Core3", dpid="0000000000000003")

        DistA1 = self.addSwitch("Dist1", dpid="0000000000000004")
        DistA2 = self.addSwitch("Dist2", dpid="0000000000000005")
        DistB1 = self.addSwitch("Dist3", dpid="0000000000000006")
        DistB2 = self.addSwitch("Dist4", dpid="0000000000000007")
        DistC1 = self.addSwitch("Dist5", dpid="0000000000000008")
        DistC2 = self.addSwitch("Dist6", dpid="0000000000000009")

        AccessA1 = self.addSwitch("Access1", dpid="0000000000000010")
        AccessA2 = self.addSwitch("Access2", dpid="0000000000000011")
        AccessB1 = self.addSwitch("Access3", dpid="0000000000000012")
        AccessB2 = self.addSwitch("Access4", dpid="0000000000000013")
        AccessC1 = self.addSwitch("Access5", dpid="0000000000000014")
        AccessC2 = self.addSwitch("Access6", dpid="0000000000000015")
        
        info("*** Adding host links\n")
        self.addLink(HostA11, AccessA1, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostA12, AccessA1, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostA21, AccessA2, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostA22, AccessA2, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB11, AccessB1, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB12, AccessB1, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB21, AccessB2, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB22, AccessB2, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostC11, AccessC1, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostC12, AccessC1, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostC21, AccessC2, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostC22, AccessC2, port1=1, port2=2, bw=100, delay='2ms', use_hfsc=True)

        info("*** Adding switch links\n")
        self.addLink(DistA1, AccessA1, port1=1, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistA2, AccessA1, port1=1, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistA1, AccessA2, port1=2, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistA2, AccessA2, port1=2, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB1, AccessB1, port1=1, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB2, AccessB1, port1=1, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB1, AccessB2, port1=2, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB2, AccessB2, port1=2, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistC1, AccessC1, port1=1, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistC2, AccessC1, port1=1, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistC1, AccessC2, port1=2, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistC2, AccessC2, port1=2, port2=4, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(DistA1, DistA2, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB1, DistB2, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistC1, DistC2, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)

        self.addLink(DistA1, CoreA, port1=4, port2=1, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistA2, CoreA, port1=4, port2=2, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistB1, CoreB, port1=4, port2=1, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistB2, CoreB, port1=4, port2=2, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistC1, coreC, port1=4, port2=1, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistC2, coreC, port1=4, port2=2, bw=1000, delay='0.5ms', use_hfsc=True)

        # Core backbone: connect all core switches so the hierarchy is one network.
        self.addLink(CoreA, CoreB, port1=3, port2=3, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(CoreB, coreC, port1=4, port2=3, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(CoreA, coreC, port1=4, port2=4, bw=1000, delay='0.5ms', use_hfsc=True)


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
    info("\n*** Network is running. Type 'pingall' or 'h1 ping h2'.\n")
    info("    For ECMP: use dijkstra_multipath or kshortest controller.\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    run()
