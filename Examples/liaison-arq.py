# Simulation script for Nessi: ARQ protocols
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

"""Laboratory TLI: Retransmission strategies (ARQ).

This file configures a network with two hosts, interconnected by a single
full duplex link. The link can simulate bit errors. Its data rate and
propagation delay may be changed.
The source application on one host periodically transmits fixed-size packets
to the sink application on the other host. The data link protocol can use the
ARQ methods
- 'Stop-and-go',
- 'Go-back-n' (Sliding window protocol)
- or 'Selective repeat request'
to manage the retransmission of erroneous frames. A CRC32 checksum is used to
test if the frame is correct.

Collected statistics are:
- throughput : effective transmission rate (correct packets) seen by the
               sink application.
- total packets : total number of packets sent by the source.
- retransmissions : number of retransmissions by the sender.
- crc errors : number of packets with a wrong checksum, seen by the sink DLC.
- sequence errors : number of packets refused due to a wrong sequence number.
"""

from nessi.simulator import *
from nessi.nodes import Host
from nessi.media import ErrorPtPLink
from nessi.devices import NIC
from nessi.dlc import FullDuplexPhy
from nessi.arq import StopAndGoDL, GoBackNDL, SelectiveRepeatDL
from nessi.trafficgen import DLFlooder, TrafficSink
try:
    import psyco
    psyco.full()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Create the network
link = ErrorPtPLink()
hosts=[]
# Create two nodes
for i in range(2):
    h = Host()
    h.hostname = "host"+str(i+1)
    niu = NIC()
    h.addDevice(niu,"eth0")
    niu.addProtocol(FullDuplexPhy(), "phy")
    niu.addProtocol(StopAndGoDL(), "dl") # CHANGE HERE FOR A DIFFERENT ARQ
    h.eth0.attachToMedium(link, 1000000.0*i) # Length: 1000 km
    hosts.append(h)

# For convenience, use short variable names for the hosts
h1,h2 = hosts

# Connect the source and the sink
source = DLFlooder()
h1.addProtocol(source, "app")
source.registerLowerLayer(h1.eth0.dl)
h1.eth0.dl.registerUpperLayer(source)

sink = TrafficSink()
h2.addProtocol(sink, "app")
h2.eth0.dl.registerUpperLayer(sink)

# ---------------------------------------------------------------------------
# Define statistics to be traced

def throughput():
    if TIME() > 0:
        return sink.octetsReceived*8 / TIME()
    else:
        return 0

def srcTotPackets():
    return source.pdusTransmitted

def retransmissions():
    return h1.eth0.dl.packetRetransmissions

def crcErrors():
    return h2.eth0.dl.crcErrors

def seqErrors():
    return h2.eth0.dl.sequenceErrors

NEW_SAMPLER("throughput",throughput,1.0)
NEW_SAMPLER("total packets",srcTotPackets,1.0)
NEW_SAMPLER("retransmissions", retransmissions, 1.0)
NEW_SAMPLER("crc errors", crcErrors, 1.0)
NEW_SAMPLER("sequence errors", seqErrors, 1.0)

# ===========================================================================
# MODIFY THE SIMULATION PARAMETERS HERE

# SOURCE
# ------
# Set the packet length (in bytes) of the source
source.setPDUSize(100) # 100 bytes payload

# LINK
# ----
# Set the data rate of the link interfaces (in bits/s)
dataRate = 1e6
h1.eth0.phy.setDataRate(dataRate)
h2.eth0.phy.setDataRate(dataRate)

# Set the propagation delay of the link.
# The link is 1000 km long and we cannot easily change this.
# But we can adapt the signal speed to obtain the required propagation delay.
propDelay = 0.01 # in seconds
link.signalSpeed = 1000000.0 / propDelay 

# Set the error model of the link
# Use the bernoulli error model with the required Bit Error Rate.
# A BER of 0.0 gives an error free link, of course.
BER = 0.0001
link.errorModel('bernoulli', BER)

# ARQ STRATEGIES (Data link layer)
# -------------------------------
# Set the retransmission timeout
timeout = 0.021
h1.eth0.dl.retransmissionTimeout = timeout
h2.eth0.dl.retransmissionTimeout = timeout

# Set the sliding window size (Only for GoBackNDL, and SelectiveRepeatDL)
window = 1
#h1.eth0.dl.setWindowSize(window)
#h2.eth0.dl.setWindowSize(window)
# ===========================================================================
# Run the simulation

source.start()
RUN(10000)
