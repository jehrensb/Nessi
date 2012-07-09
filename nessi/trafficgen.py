# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: October 2003
#
# Copyright (c) 2003-2007 Juergen Ehrensberger
#
# This file is part of Nessi.
#
# Nessi is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License.
#
# Nessi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Nessi; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""Implementation of different traffic generators."""

__all__ = ["TrafficSource", "CBRSource", "PoissonSource", "WebSource", "Sink"]

import struct
from sys import maxint
import random
from simulator import TIME, SCHEDULEABS, SCHEDULE
from netbase import HigherLayerProtocol, ProtocolEntity


class TrafficSource(HigherLayerProtocol):
    """Base class for traffic generators."""

    _uniquePDUId = 0
    """Used to generate unique bitstreams."""
    _host = None
    """Host on which the source is installed."""
    
    def install(self, host, protocolName):
        """Install the source on a node.

        Arguments:
          host:Host -- Node on which self is installed
          protocolName:String -- Name under which self is installed on the
                                 node.
        Return value: None.
        """
        self.fullName = host.hostname + "." + protocolName
        self._host = host

    def registerLowerLayer(self, lowerLayerEntity):
        """Connect to a lower layer entity to send packets.

        PDUs can then be sent using the lowerLayerEntity send method.
        Only a single lower layer may be registered.
        """
        self._lowerLayers = lowerLayerEntity

    def registerUpperLayer(self, *args):
        """Must not be called for an application layer protocol."""
        raise RuntimeError("registerUpperLayer method not available.")
    
    def start(self, time=0.0):
        """Start to generate traffic after a delay.

        Schedule a call to generate at the given time.
        """
        SCHEDULEABS(time, self.generate)

    def generate(self):
        """Method that is peridically scheduled to generate a new packet.

        This method must be implemented by a subclass to implement the
        actual traffic model.
        It must call self.send to actually send the packet.
        """
        virtual

    def send(self, bitstream):
        """Send the generated bitstream to the lower layer."""
        self._lowerLayers.send(bitstream)

    def _uniqueBitstream(self, length):
        """Generate a unique bitstream of the given length, in bytes."""
        bitstream =struct.pack("ii", id(self),self._uniquePDUId)
        self._uniquePDUId += 1
        if self._uniquePDUId > maxint:
            self._uniquePDUId = 0
        lth = len(bitstream)
        return bitstream + "x"*(length-lth) # Fill with 'xxx...' is needed

    def receive(self, *args):
        """Must not be called by the lower layer."""
        raise RuntimeError("Receive method of traffic source called.")


class CBRSource(TrafficSource):
    """Traffic generator for constant bitrate traffic.

    A fixed size PDU is generated at regular time intervals.
    """
    def __init__(self, pduSize=0, interarrival=0):
        """Initialize the generator.

        Arguments:
          pduSize:Integer -- Length of the generated PDUs, in bytes.
          interarrival:Float -- Time between consecutive PDUs, in seconds.
        Return value: None.
        """
        self._pduSize = pduSize
        self._interarrival = interarrival

        ### Statistics
        self.octetsTransmitted = 0
        """Count of transmitted octets."""
        self.pdusTransmitted = 0
        """Count of transmitted PDUs."""

    def setPDUSize(self, pduSize):
        """Change the size of the generated PDUs, measured in bytes."""
        self._pduSize = pduSize

    def setInterarrival(self, interarrival):
        """Set the time between consecutive PDUs, measured in seconds."""
        self._interarrival = interarrival

    def start(self, time=0.0):
        SCHEDULEABS(time, self.generate)

    def generate(self):
        self.send(self._uniqueBitstream(self._pduSize))
        self.octetsTransmitted += self._pduSize
        self.pdusTransmitted += 1
        SCHEDULE(self._interarrival, self.generate)


class PoissonSource(TrafficSource):
    """Traffic generator for Poisson traffic.

    PDU sizes and interarrivals have an exponential distribution.
    """
    def __init__(self, meanPDUSize=0, meanInterarrival=0):
        """Initialize the generator.

        Arguments:
          meanPDUSize:Float -- Mean length of generated PDUs, in bytes.
          meanInterarrival:Float -- Mean time between PDUs, in seconds.
        Return value: None.
        """
        self._pduSizeRNG = lambda : random.expovariate(1.0/meanPDUSize)
        self._interarrivalRNG = lambda : random.expovariate(1.0/meanInterarrival)

        ### Statistics
        self.octetsTransmitted = 0
        """Count of transmitted octets."""
        self.pdusTransmitted = 0
        """Count of transmitted PDUs."""

    def setPDUSize(self, meanPDUSize):
        """Change the mean size of the generated PDUs, measured in bytes."""
        self._pduSizeRNG = lambda : random.expovariate(1.0/meanPDUSize)

    def setInterarrival(self, meanInterarrival):
        """Set the mean time between consecutive PDUs, measured in seconds."""
        self._interarrivalRNG = lambda : random.expovariate(1.0/meanInterarrival)

    def start(self, time=0.0):
        SCHEDULEABS(time+self._interarrivalRNG(), self.generate)

    def generate(self):
        length = max(9,int(self._pduSizeRNG()))
        self.send(self._uniqueBitstream(length))
        self.octetsTransmitted += length
        self.pdusTransmitted += 1
        SCHEDULE(self._interarrivalRNG(), self.generate)


class WebSource(TrafficSource):
    """On/Off source to simulate http/1.1 replies.

    This traffic generator simulates the behavior of http connections.
    It remains silent during an Off time with a truncated Pareto distribution.
    Then it starts to transmit a web page whose size has a truncated LogNormal
    distribution. During the transmission, PDUs of constant size are sent at
    a constant rate. As soon as the entire page has been sent, the generator
    goes into the off-state again for a random time.

    The superposition of many of these sources generated self-similar traffic.
    For further information refer to the articles:
    P. Barford and M. Crovella, 'Generating representative web workloads for
      network an server performance evaluation', Proc. 1998 ACM SIGMETRICS
      Intl. Conf. On Measurement and Modeling of Computer Systems, pp 151-160,
      July 1998.
    N. K. Shankaranarayanan, Zhimei Jian, and Partho Mishra, 'User-Perceived
      Performance of Web-browsing and Interactive Data in HFC Cable Access
      Networks'. @@@@ where published?
    """
    
    def __init__(self):
        """Initialize the traffic generator with the default parameters.

        The parameters are taken from Shankaranarayanan et al.
        """
        self.setPageSize(mean=9.5, stdev=1.8, minSize=100, maxSize=int(20e6))
        self.setOffTime(shape=1.5, scale=1.0, minTime=2.0, maxTime=3600.0)
        self.setOnRate(rate=1e6)
        self.setPDUSize(size=512)

        ### Statistics
        self.octetsTransmitted = 0
        """Count of transmitted octets."""
        self.pdusTransmitted = 0
        """Count of transmitted PDUs."""
        self.pagesTransmitted = 0
        """Count of pages whose transmission has been completed."""

    def setPageSize(self, mean=9.5, stdev=1.8, minSize=100, maxSize=int(20e6)):
        """Set the parameters of page size distribution (LogNormal dist.).

        Arguments:
          mean:Float -- Parameter mu of the LogNormal distribution, in bytes.
          stdev:Float -- Parameter sigma of the LogNormal distribution.
          minSize:Integer -- Minimum page size in bytes.
          maxSize:Integer -- Maximum page size in bytes.
        Return value: None.
        """
        self._pageSizeRNG = lambda : random.lognormvariate(mean, stdev)
        self._pageSizeMin = minSize
        self._pageSizeMax = maxSize

    def setOffTime(self, shape=1.0, scale=2.0, minTime=2.0, maxTime=3600.0):
        """Set the parameters of the OFF time distribution (Pareto dist.)

        Arguments:
          shape:Float -- Shape parameter of the Pareto distribution.
          scale:Float -- Scale parameter of the Pareto distribution.
          minTime:Float -- Minimum OFF time, in seconds.
          maxTime:Float -- Maximum OFF time, in seconds.
        Return value: None.
        """
        # Attention: python random uses scale==1, simply multiply with scale
        self._offTimeRNG = lambda : random.paretovariate(shape)*scale
        self._offTimeMin = minTime
        self._offTimeMax = maxTime

    def setOnRate(self, rate=1e6):
        """Set the transmission rate during the ON phase in bit/s."""
        self._onRate = rate

    def setPDUSize(self, size=512):
        """Set the size of each PDU during the ON phase, in bytes."""
        self._pduSize = size

    def start(self, time=0.0):
        SCHEDULEABS(time, self.generate)

    def generate(self):
        """Schedule a new page transmission after a random OFF time."""
        offTime = self._offTimeRNG()
        offTime = min(offTime, self._offTimeMax)
        offTime = max(offTime, self._offTimeMin)
        SCHEDULE(offTime, self._sendPage)

    def _sendPage(self):
        """Determine a random page size and start sending it."""
        pageSize = int(self._pageSizeRNG())
        pageSize = min(pageSize, self._pageSizeMax)
        pageSize = max(pageSize, self._pageSizeMin)
        self._pageSize = pageSize
        self._sendPacket()

    def _sendPacket(self):
        """Send PDUs to the lower layer until the whole page is transmitted.

        At the end, start a new OFF period by calling generate."""
        length = min(self._pageSize, self._pduSize)
        bitstream = self._uniqueBitstream(length)
        self.send(bitstream)
        self.octetsTransmitted += length
        self.pdusTransmitted += 1

        self._pageSize -= length
        if self._pageSize > 0:
            delay = (self._pduSize*8.0) / self._onRate
            SCHEDULE(delay, self._sendPacket)
        else:
            self.pagesTransmitted += 1
            self.generate()


class DLFlooder(TrafficSource):
    """Sent fixed sized packets to a DL protocol entity as fast as possible.

    Sent a new packet as soon as the DL signals that a new packet can be sent.
    """

    def __init__(self, pduSize=0):
        """Initialize the generator.

        Arguments:
          pduSize:Integer -- Length of the generated PDUs, in bytes.
        Return value: None.
        """
        self._pduSize = pduSize

        ### Statistics
        self.octetsTransmitted = 0
        """Count of transmitted octets."""
        self.pdusTransmitted = 0
        """Count of transmitted PDUs."""

    def setPDUSize(self, pduSize):
        """Change the size of the generated PDUs, measured in bytes."""
        self._pduSize = pduSize
    
    def generate(self):
        """Generate a new packet and send it to the DL."""
        assert(self._lowerLayers._device.XOFF == False)

        while self._lowerLayers._device.XOFF == False:
            self.send(self._uniqueBitstream(self._pduSize))
            self.octetsTransmitted += self._pduSize
            self.pdusTransmitted += 1

    def sendStatus(self, status, bitstream):
        """Called by the DL layer to signal that a packet has been sent.

        Try to send the next one.
        """
        # @@@ FIXME: This is not clean. Better use a queuing layer.
        if self._lowerLayers._device.XOFF == False:
            self.generate()


class TrafficSink(ProtocolEntity):
    """Traffic sink which counts and discards received PDUs."""
    
    octetsReceived = 0L
    """Count of received octets."""
    pdusReceived = 0
    """Count of received PDUs."""
    sequenceErrors = 0
    """Number of packets received out of order or lost or duplicated.
    Only if checkSequence is on."""
    
    _checkSequence = False
    _VS = None

    def install(self, host, protocolName):
        """Install the sink on a host under a protocol name.

        The host is responsible for connecting the connecting the
        protocolName to a lower layer protocol such that it delivers the
        PDUs by calling the sinks receive method.
        """
        self.host = host
        self.fullName = host.hostname + "." + protocolName

    def receive(self, bitstream):
        """Update statistics and discard the PDU."""
        self.pdusReceived += 1
        self.octetsReceived += len(bitstream)
        if self._checkSequence:
            srcId, pduId = struct.unpack("ii", bitstream[:8])
            vs = self._VS.get(srcId, -1)
            if vs >= 0:
                if vs + 1 != pduId:
                    if (vs+1) % maxint != pduId:
                        print "Sink: sequence error", vs, pduId
                        self.sequenceErrors += 1
            self._VS[srcId] = pduId

    def send(self, *args):
        """Must not be called for a sink."""
        raise RuntimeError("Send method of traffic sink called.")

    def setCheckSequence(self, activate):
        """Enable or disable the check if the packets are in the correct order.

        Enabling this check required that the sources uses the method
        _uniqueBitstream to generate packets.
        """
        if activate:
            self.sequenceErrors = 0
            self._VS = {}
        self._checkSequence = activate
