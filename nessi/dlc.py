# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: February 2005
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

"""
Defines data link and physical layer protocols for simple NIUs like a
simple point-to-point links.
"""

__all__ = ["PointToPointPhy", "PointToPointDL"]

from simulator import SCHEDULE
from netbase import Device, PhyLayer, DLBottom, DLTop


class FullDuplexPhy(PhyLayer):
    """Simple PhyLayer entity for full duplex transmission at a fixed rate.

    It requires a complete dl protocol entity as higher layer, not a MAC."""

    _dataRate = 1e6
    """Data rate of the NIU, in bit/s."""
    
    def setDataRate(self, dataRate):
        """Set the data rate of the physical interface."""
        self._dataRate = dataRate

    def getDataRate(self):
        """Return the data rate of the physical interface."""
        return self._dataRate

    def newChannelActivity(self):
        """Called by the medium when an NIU starts transmitting.

        Since this link works in full duplex, do nothing."""
        pass

    def receive(self, bitstream):
        """Receive the data from the medium and deliver it to the DL entity.

        Called by the medium to deliver data.
        """
        self._niu.dl.receive(bitstream)

    def send(self, bitstream):
        """Simulate the transmission of the data on the medium.

        Schedule the call to inform the DL entity when finished.
        
        Arguments:
          bitstream:Bitstream -- Block of data to transmit onto the medium.
        Return value: None.
        """
        self._niu.medium.startTransmission(self._niu)
        transmissionDelay = len(bitstream)*8 / self._dataRate
        SCHEDULE(transmissionDelay,
                 self._niu.medium.completeTransmission,(self._niu, bitstream))
        SCHEDULE(transmissionDelay, self._niu.dl.sendStatus,(0, bitstream))

        
class PointToPointDL(DLTop,DLBottom):
    """Simple, non-reliable data link layer entity. 

    A received packet is simply forwarded to all network layer entities
    that have been registered via the registerUpperLayer method.
    """

    octetsReceivedOK = 0
    """Count of data octets successfully received."""
    octetsTransmittedOK = 0
    """Count of data octets successfully sent."""        
    octetsTransmittedError = 0
    """Count of data octets not sent because of errors."""

    def __init__(self):
        self._upperLayers = []

    def install(self, device, protocolName):
        if isinstance(device, Device):
            self._device = device
        else:
            raise TypeError("DL layer entity must be installed on a device")
        if protocolName != "dl":
            raise NameError("DL layer entity must be installed under "
                            "the name 'dl'")
        self._protocolName = "dl"
        self.fullName = device.fullName + ".dl"

        # Start accepting frames
        self._device.XOFF = False

    def registerUpperLayer(self, upperProtocolEntity, protocolType=None):
        """Register an entity to which received PDUs are delivered.

        The only protocol type accepted is None.
        """
        assert (protocolType == None)
        self._upperLayers.append(upperProtocolEntity)

    def send(self, bitstream):
        """Pass the bitstream to the PHY, without encapsulation.

        This combines the send functions of DLTop and DLBottom.
        Only one packet can be sent at a time. It is an error if the higher
        layer tries to send another packet while the previous transmission is
        not yet finished. 
        """
        assert (self._device.XOFF == False and not self._sendBuffer)
        self._device.XOFF = True
        self._sendBuffer = bitstream
        self._device.phy.send(bitstream)
        return 0

    def sendStatus(self, status, bitstream):
        """Called by the phy layer when a transmission is completed.

        Update the statistics and inform the higher layer.
        """
        if status == 0:
            # Transmission successfully completed
            self.octetsTransmittedOK += len(bitstream)
        else:
            # Transmission error. Simply discard the frame
            self.octetsTransmittedError += len(bitstream)
        self._sendBuffer = None
        self._device.XOFF = False

    def receive(self, bitstream):
        """Deliver the received data to the registered upper layer protocol.

        This combines the receive functions of DLBottom and DLTop."""
        self.octetsReceivedOK += len(bitstream)
        for upperLayer in self._upperLayers:
            upperLayer.receive(bitstream)
