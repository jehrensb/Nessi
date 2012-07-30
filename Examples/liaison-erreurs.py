# Simulation script for Nessi: error control protocols
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

"""Laboratory TLI: Error detecting codes.

This file configures a network with two hosts, interconnected by two links:
an error free link and a link that simulated bit errors.
The source application on one host periodically transmits identical packets
with checksums over both links. The sink application compares both packets and
tests whether the checksum was able to detect any bit errors.
Collected statistics are:
- undetected errors: count of undetected errors per number of erroneous bits
                     in the packet
- undetected bursts: count of undetected errors per length of the error burst
                     in the packet
- total errors: total number of errors (detected and undetected) per number
                of erroneous bits in the packet
- total bursts: total number of errors (detected and undetected) per error
                burst length
"""

from nessi.simulator import *
from nessi.nodes import Host
from nessi.devices import NIC
from nessi.dlc import FullDuplexPhy, PointToPointDL 
from nessi.media import PtPLink
from nessi.media import ErrorPtPLink
from nessi.checksums import *
try:
    import psyco
    psyco.full()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Create the network

goodlink = PtPLink()
badlink = ErrorPtPLink()

hosts=[]
# Create two nodes
for i in range(2):
    h = Host()
    h.hostname = "host"+str(i)
    # On each node, create two interfaces, eth0 and eth1
    for j in range(2):
        niu = NIC()
        h.addDevice(niu,"eth"+str(j))
        niu.addProtocol(FullDuplexPhy(), "phy")
        niu.addProtocol(PointToPointDL(), "dl")
    # eth0 is attached to the errored link, eth1 to the error-free link
    h.eth0.attachToMedium(badlink, 100.0*i)
    h.eth1.attachToMedium(goodlink, 10.0*i) # The good link is shorter
    hosts.append(h)

# Give the hosts good names
h1,h2 = hosts

# Connect the source and the sink
source = ChksumSource()
h1.addProtocol(source, "app")
source.registerLowerLayer(h1.eth0.dl)
source.registerLowerLayer(h1.eth1.dl)

sink = ChksumSink()
h2.addProtocol(sink, "app")
h2.eth0.dl.registerUpperLayer(sink)
h2.eth1.dl.registerUpperLayer(sink)

# ---------------------------------------------------------------------------
# Define statistics to be traced

def errorsampler():
    result = ""
    for numErrors,undetected in sink.bitErrorsUndetected.items():
        detected = sink.bitErrorsDetected.get(numErrors,0)
        result += "%d,%f;"%(numErrors, undetected/float(undetected+detected))
    return result[:-1]

def burstsampler():
    result = ""
    for numErrors,undetected in sink.burstsUndetected.items():
        detected = sink.burstsDetected.get(numErrors,0)
        result += "%d,%f;"%(numErrors, undetected/float(undetected+detected))
    return result[:-1]

def bursts():
    dict={}
    for numErrors,count in sink.burstsUndetected.items():
        dict[numErrors]=count
    for numErrors,count in sink.burstsDetected.items():
        dict[numErrors] = dict.get(numErrors,0)+count
    result = ';'.join(["%d,%f"%(x,y) for x,y in dict.items()])
    return result

def errors():
    dict={}
    for numErrors,count in sink.bitErrorsUndetected.items():
        dict[numErrors]=count
    for numErrors,count in sink.bitErrorsDetected.items():
        dict[numErrors] = dict.get(numErrors,0)+count
    result = ';'.join(["%d,%f"%(x,y) for x,y in dict.items()])
    return result

NEW_SAMPLER("undetected errors",errorsampler,1.0)
NEW_SAMPLER("undetected bursts",burstsampler,1.0)
NEW_SAMPLER("total bursts", bursts, 1.0)
NEW_SAMPLER("total errors", errors, 1.0)

# ===========================================================================
# MODIFY THE SIMULATION PARAMETERS HERE

# Set the packet interval and the packet length (in bits) of the source
source.setParameters(interval=0.001, length=96) 

# Set the checksums to use by the source and the sink.
# You may use
# - IPChksum and checkIPChksum
# - doubleParityChksum and checkDoubleParityChksum
# - polynomialChksum and checkDoubleParityChksum.
# For the polynomialChksum, you have to provide a polynomial in the form
# of the list of coefficients. To use the polynomial x**8 + x**2 + 1 do e.g.:
#   mycrc = [1,0,0,0,0,0,1,0,1]
#   source.useChksum(lambda x: polynomialChksum(x,mycrc)) and
#   sink.useChksum(lambda x: checkPolynomialChksum(x,mycrc))
crc16 = [1, 1,0,0,0,0,0,0,0, 0,0,0,0,0,1,0,1]
ccitt = [1, 0,0,0,1,0,0,0,0, 0,0,1,0,0,0,0,1]
crc32 = [1, 0,0,0,0,0,1,0,0, 1,1,0,0,0,0,0,1, 0,0,0,1,1,1,0,1, 1,0,1,1,0,1,1,1]
mycrc = [1,1,0,0,0,0,0,0,1]
source.useChksum(IPChksum)
sink.useChksum(checkIPChksum)

# Set the error model of the link
# You may use uniform or bernoulli errors:
# badlink.errorModel('uniform',0,10): 0 to 10 bits may be modified, and all
#                                     numbers of bit errors are equally likely
#badlink.errorModel('bernoulli',0.001): Independent bit errors with a BER=0.001
badlink.errorModel('bernoulli', 0.07)

# ===========================================================================
# Run the simulation

def printErrors(a,b,c=None):
    print a,b,c
REGISTER_LISTENER("undetected errors", printErrors)

source.start()
RUN(1000)
