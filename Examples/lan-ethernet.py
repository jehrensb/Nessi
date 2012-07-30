# Simulation script for Nessi: Ethernet simulation
# 
# Copyright (c) 2003-2007 Juergen Ehrensberger
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Laboratory TLI: CSMA/CD

This file configures a shared Ethernet network with multiple stations.
The performance of the CSMA/CD protocol can be evaluated.
The source application generates new packets at a configurable rate.

Collected statistics are:
- "throughput": Line plot: total throughput in b/s
- "sequence errors": Line plot: Number of lost or duplicated packets, due to
erreneous behavior of the MAC layer.
- "waiting packets": Line plot: Total number of packets waiting for
transmission at all nodes.
- "packet rate": Bar plot: Rate of packet transmissions per station.
- "collision frames": Bar plot: Fraction of transmitted frames that suffered 1
or more collisions, per station
- "channel activities": Bar plot: Distribution of simultaneous accesses to the
channel, in time. 

"""

from nessi.simulator import *
from nessi.nodes import Host
from nessi.media import Bus
from nessi.devices import NIC
from nessi.ethernet import PHY, MAC, LLC, HALF_DUPLEX, FULL_DUPLEX
from nessi.trafficgen import DLFlooder, PoissonSource, TrafficSink
try:
    import psyco
    psyco.full()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Helper functions
class PseudoNW:
    def __init__(self):
        self.upperLayer = None
    def setSrcMAC(self, mac):
        self.srcMAC = mac
    def setDstMAC(self,mac):
        self.dstMAC = mac
    def setProtocolType(self,type):
        self.protocolType = type
    def registerLowerLayer(self, lowEntity):
        self.lowerLayer = lowEntity
        self._device = lowEntity._device
    def registerUpperLayer(self, upEntity):
        self.upperLayer = upEntity
    def install(self, host, protocolName):
        self.fullName = host.hostname + "." + protocolName
        self._host = host
    def send(self, bitstream):
        if len(bitstream) > 1500:
            bitstream = bitstream[:1500]
        self.lowerLayer.send(bitstream, self.dstMAC, self.srcMAC,
                             self.protocolType)
    def sendStatus(self,status,bitstream):
        if self.upperLayer:
            self.upperLayer.sendStatus(status,bitstream)
    def receive(self,bitstream):
        if self.upperLayer:
            self.upperLayer.receive(bitstream)
# ---------------------------------------------------------------------------
# Create the network
link = Bus()
numHosts = 31 # CHANGE HERE FOR THE NUMBER OF NODES
hosts=[]
for i in range(numHosts):
    h = Host()
    h.hostname = "host"+str(i)
    niu = NIC()
    h.addDevice(niu,"eth0")
    niu.addProtocol(PHY(), "phy")
    niu.addProtocol(MAC(), "mac")
    niu.addProtocol(LLC(), "dl")
    h.addProtocol(PseudoNW(), "nw")
    h.nw.setSrcMAC(h.eth0.mac.address)
    h.nw.setProtocolType(2048)
    h.nw.registerLowerLayer(niu.dl)
    h.eth0.dl.registerUpperLayer(h.nw, 2048)
    h.eth0.attachToMedium(link, i*1.0) # CHANGE HERE FOR THE BUS LENGTH
    hosts.append(h)

# Attach a traffic sink to the first node
server = hosts[0]
sink = TrafficSink()
server.addProtocol(sink, "app")
sink.setCheckSequence(True)
server.nw.registerUpperLayer(sink)
serverMAC = server.eth0.mac.address

# Attach a traffic source DLFlooder to all other nodes
for h in hosts[1:]:
    source = PoissonSource()
    source.setInterarrival(0.1)
    source.setPDUSize(100)
    h.addProtocol(source, "app")
    source.registerLowerLayer(h.nw)
    h.nw.setDstMAC(serverMAC)

# ---------------------------------------------------------------------------
# Define statistics to be traced

class StatSampler:
    startTime = 0.0
    channelOccupation = {}
    channelSamples = 0.0

    def resetStats(self):
        self.startTime = TIME()
        self.channelOccupation = {}
        self.channelSamples = 0.0
        
        for h in hosts:
            h.app.octetsReceived = 0
            h.eth0.dl.packetsSent = 0
            h.eth0.dl.packetRetransmissions = 0

    def throughput(self):
        """Throughput as seen by the sink on the server."""
        if TIME() > self.startTime:
            return server.app.octetsReceived*8 / (TIME()-self.startTime)
        else:
            return 0

    def sequenceErrors(self):
        """Number of sequence errors (lost or duplicated packets) seen
        by the server."""
        if TIME() > self.startTime:
            return server.app.sequenceErrors
        else:
            return 0
        
    def packetRate_perSrc(self):
        """Packet per second, for each source. Suitable for a bar plot."""
        result = " "
        if TIME() > self.startTime:
            for i in range(numHosts):
                result += "%d,%f;"%(i,hosts[i].eth0.mac.framesTransmittedOK
                                    / (TIME()-self.startTime))
        return result[:-1]

    def collisionFrames_perSrc(self):
        """Fraction of transmitted frames that suffered 1 or more collisions.
        """
        result = " "
        for i in range(numHosts):
            sent = float(hosts[i].eth0.mac.framesTransmittedOK)
            if sent:
                colFrames = (hosts[i].eth0.mac.singleCollisionFrames +
                             hosts[i].eth0.mac.multipleCollisionFrames)
                result += "%d,%f;"%(i,colFrames /sent)
        return result [:-1]
        
    def totalQueueLength(self):
        """Total packet number generated by the sources but not transmitted."""
        queue = 0
        for h in hosts:
            queue += len(h.eth0.dl._transmissionBuffer)
        return queue

    def channelActivities(self):
        """Frequency of different number of concurrent transmission on the
        channel. Suitable for bar plots."""
        self.channelSamples += 1
        numTr = server.eth0.phy._receiveActivities
        self.channelOccupation[numTr] = self.channelOccupation.get(numTr,0)+1
        result = ';'.join(["%d,%f"%(x,y/self.channelSamples)
                           for x,y in self.channelOccupation.items()])
        return result

stats = StatSampler()
NEW_SAMPLER("throughput",stats.throughput,0.1, 'exponential') # Line plot
NEW_SAMPLER("sequence errors",stats.sequenceErrors,0.1, 'exponential')#Line
NEW_SAMPLER("waiting packets",stats.totalQueueLength,0.1, 'exponential')#Line

NEW_SAMPLER("packet rate",stats.packetRate_perSrc,0.1, 'exponential') #Bar plot
NEW_SAMPLER("collision frames",
            stats.collisionFrames_perSrc,0.1,'exponential') # Bar
NEW_SAMPLER("channel activities",
            stats.channelActivities,0.1,'exponential') # Bar plot

# ===========================================================================
# MODIFY THE SIMULATION PARAMETERS HERE

# SOURCE
# ------
# Set the parameters of the source
meanPDUSize = 100 # Mean packet size in bytes
meanInterarrival = 0.02 # Mean time between sending packets
for h in hosts[1:]:
    h.app.setPDUSize(meanPDUSize) # Exponentially distributed packet size
    h.app.setInterarrival(meanInterarrival) # Exponentially distributed

# LINK
# ----
dataRate = 10e6 # 10 Mb/s
for h in hosts:
    h.eth0.phy.setDataRate(dataRate)
    h.eth0.phy.setDuplexMode(HALF_DUPLEX)
    
# ===========================================================================
# Define functions that allow the user to interactively change the traffic
# during the simulation
def pdusize(pduSize):
    """Changes the mean pdu size of all sources."""
    global meanPDUSize
    meanPDUSize = pduSize
    for h in hosts[1:]:
        h.app.setPDUSize(pduSize)
    stats.resetStats()
    rate = len(hosts[1:]) * meanPDUSize * 8 / meanInterarrival
    print "Total rate: ", rate, " bits/s"

def interarr(interarrival):
    """Changes the mean pdu size of all sources."""
    global meanInterarrival
    meanInterarrival = interarrival
    for h in hosts[1:]:
        h.app.setInterarrival(interarrival)
    stats.resetStats()
    rate = len(hosts[1:]) * meanPDUSize * 8 / meanInterarrival
    print "Total rate: ", rate, " bits/s"
    
# ===========================================================================
# Run the simulation

for h in hosts[1:]:
    h.app.start()
RUN(100)
