#!/usr/bin/env python3

from functools import partial

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel, info
from mininet.cli import CLI


class HierarchyTopo(Topo):

    def addSwitch(self, name, **opts):
        kwargs = {"protocols": "OpenFlow13"}
        kwargs.update(opts)
        return super(HierarchyTopo, self).addSwitch(name, **kwargs)

    def __init__(self):
        Topo.__init__(self)

        HostA11 = self.addHost("Host1", ip="10.0.0.1/24")
        HostA21 = self.addHost("Host2", ip="10.0.0.2/24")

        HostB11 = self.addHost("Host3", ip="10.0.0.3/24")
        HostB21 = self.addHost("Host4", ip="10.0.0.4/24")

        info("*** Adding switches\n")
        # Hanya menggunakan Core A dan Core B
        CoreA = self.addSwitch("Core1", dpid="0000000000000001")
        CoreB = self.addSwitch("Core2", dpid="0000000000000002")
        CoreC = self.addSwitch("Core3", dpid="0000000000000003")


        DistA1 = self.addSwitch("Dist1", dpid="0000000000000004")
        DistA2 = self.addSwitch("Dist2", dpid="0000000000000005")
        DistB1 = self.addSwitch("Dist3", dpid="0000000000000006")
        DistB2 = self.addSwitch("Dist4", dpid="0000000000000007")

        AccessA1 = self.addSwitch("Access1", dpid="0000000000000010")
        AccessA2 = self.addSwitch("Access2", dpid="0000000000000011")
        AccessB1 = self.addSwitch("Access3", dpid="0000000000000012")
        AccessB2 = self.addSwitch("Access4", dpid="0000000000000013")
        info("*** Adding host links\n")
        # Setiap Access Switch hanya memegang port2=1 untuk 1 host saja
        self.addLink(HostA11, AccessA1, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostA21, AccessA2, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB11, AccessB1, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)
        self.addLink(HostB21, AccessB2, port1=1, port2=1, bw=100, delay='2ms', use_hfsc=True)

        info("*** Adding switch links\n")
        # Link dari Distribution ke Access (Port host yang kosong tidak dipakai)
        self.addLink(DistA1, AccessA1, port1=1, port2=3, bw=50, delay='1ms', use_hfsc=True)
        self.addLink(DistA2, AccessA1, port1=1, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistA1, AccessA2, port1=2, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistA2, AccessA2, port1=2, port2=4, bw=500, delay='1ms', use_hfsc=True)
        
        self.addLink(DistB1, AccessB1, port1=1, port2=3, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB2, AccessB1, port1=1, port2=4, bw=500, delay='1ms', use_hfsc=True)
        self.addLink(DistB1, AccessB2, port1=2, port2=3, bw=1000, delay='1ms', use_hfsc=True)
        self.addLink(DistB2, AccessB2, port1=2, port2=4, bw=500, delay='1ms', use_hfsc=True)

        # Inter-distribution links
        self.addLink(DistA1, DistA2, port1=3, port2=3, bw=1000, delay='1ms', use_hfsc=True)
        self.addLink(DistB1, DistB2, port1=3, port2=3, bw=500, delay='1ms', use_hfsc=True)

        # Distribution ke Core
        self.addLink(DistA1, CoreA, port1=4, port2=1, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistA2, CoreA, port1=4, port2=2, bw=400, delay='0.5ms', use_hfsc=True)
        self.addLink(DistB1, CoreB, port1=4, port2=1, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(DistB2, CoreB, port1=4, port2=2, bw=900, delay='0.5ms', use_hfsc=True)

        # Core backbone: menghubungkan CoreA dan CoreB langsung
        self.addLink(CoreA, CoreB, port1=3, port2=3, bw=400, delay='0.5ms', use_hfsc=True)
        self.addLink(CoreB, CoreC, port1=4, port2=3, bw=1000, delay='0.5ms', use_hfsc=True)
        self.addLink(CoreC, CoreA, port1=4, port2=4, bw=1000, delay='50ms', use_hfsc=True)

def run():
    topo = HierarchyTopo()
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
