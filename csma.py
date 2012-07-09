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
MAC and LLC protocols for multiple access channels.
The implemented multiple access channels are
  - Aloha and Slotted Aloha 
  - CSMA variants
  - CSMA/CD (CSMA with collision detection, used in Ethernet)
  - CSMA/CA (CSMA with collision avoidance, used in Wireless LANs).
"""

__all__ = ["IdealRadioPhy", "AlohaDL", "CSMADL", "CSMA_CA_DL"]

from simulator import SCHEDULE, CANCEL, ACTIVITY_INDICATION, TIME
from netbase import PhyLayer
from dlc import PointToPointDL
from pdu import PDU, formatFactory
from zlib import crc32
from random import randint

class IdealRadioPhy(PhyLayer):
    """Physical layer entity for an ideal radio physical layer.

    The task of the physical layer is to accept bits from the MAC
    sublayer and to transmit them over the attached medium as well as
    to receive bits from the medium and pass them to the MAC
    The IdealRadioPhy does not simulate signal attenuation or bit errors.
    It only provides information to the MAC sublayer if the medium is idle
    or occupied (=carrier sense). Collision detect is not possible on this phy.

    Interface provided to the medium:
      - newChannelActivity -- Called by the medium when another NIU starts
                              transmitting.
      - receive -- Receive the data of a transmission from the medium.

    Interface provided to the MAC layer:
      - carrierSense -- True, if the medium is occupied, False otherwise.
      - transmitting -- Called by MAC to start or stop a transmission.
      - send -- Called by the MAC layer to transmit a block of data.
      - bittime -- Returns the time it takes to transmit a bit.
      
    Configuration interface:
      - install -- Install the protocol entity as 'phy' on a NIU.
      - setDataRate -- Set the data rate of the physical interface.
      - getDataRate -- Return the data rate of the physical interface.
    """

    def __init__(self):
        self._dataRate = 1e6
        """Data rate for transmission. In bits/s. Type: float."""

        self._receiveActivities = 0
        """Number of active incoming transmission. Type:Integer."""
        self._receiveStartTime = None
        """Start time of receive activity on the channel. Type:Float."""
        self._overlappingReceptions = False
        """Flag whether the was a collision of incoming transmissions."""
        self._transmitting = False
        """Flag whether there is currently an outgoing transmission."""
        self._transmitStartTime = None
        """Start time of the outgoing transmission. Type:Float."""
        self._transmittedData = None
        """Bitstream that has to be send onto the medium. Type:Bitstream."""
        self._completeTxEventId = None
        """Event id scheduled for the time when a transmission finishes."""

    def setDataRate(self, dataRate):
        """Set the data rate of the physical interface in bits/s."""
        self._dataRate = dataRate

    def getDataRate(self):
        """Return the data rate of the physical interface."""
        return self._dataRate
                
    def newChannelActivity(self):
        """Register a new channel activity and overlapping transmissions.

        Called by the medium when another NIU starts transmitting. The
        method determines if the new transmission causes a receive collision
        (collision with transmissions of other NIUs). Receive collisions
        are remembered to later invalidate the received data before passing
        it to the MAC.
        """
        self._receiveActivities += 1
        if self._receiveActivities == 1:
            self._receiveStartTime = TIME()
            self._overlappingReceptions = False
        else:
            self._overlappingReceptions = True

    def receive(self, bitstream):
        """Receive the data of a transmission from the medium.

        Called by the medium when the transmission of an NIU ends.
        If this was the only incoming transmission, then the received data is
        delivered to the MAC.
        If this terminates the last of several overlapping incoming
        transmissions, then corrupted data is delivered to the MAC. The length
        of the data is determined by the total time of uninterrupted reception,
        i.e., ((end of last transmission) - (start of first tx)) * data rate.

        Arguments:
          bitstream:Bitstream -- data received from the medium.
        Return value: None.
        """
                
        self._receiveActivities -= 1
        if self._receiveActivities > 0:
            return

        # All reception finished. Pass received data to the MAC.
        # If there where overlapping receptions, invalidate the data.
        bytelen=int(((TIME()-self._receiveStartTime)*self._dataRate + 0.05)/ 8)
        if self._overlappingReceptions:
            self._overlappingReceptions = False
            self._receiveStartTime = None
            bitstream = '\x00' * bytelen
        elif len(bitstream) != bytelen:
            raise ValueError("Speed mismatch on radio channel "
                             + self._niu._host.hostname + "."
                             + self._niu.devicename
                             + ".phy: received data with invalid length")
        self._niu.dl.receive(bitstream)

        # If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.dl.channelIdle()

    def carrierSense(self):
        """Return True if the channel is occupied, False otherwise."""
        return (self._receiveActivities > 0 or self._transmitting)
        
    def transmitting(self, activate):
        """Start or stop a transmission.

        This method is called by the MAC layer with the argument
        activate=True to prepare the PHY layer for the transmission of data.
        It is called with an argument activate=False to interrupt or to
        finish a transmission. MAC may interrupt a transmission after it has
        been informed of a collision. Finishing occurs when the MAC has been
        informed that PHY has sent all data to the medium.

        Arguments:
          activate:Boolean -- start or stop transmitting.
        Return value: None.
        """
        if activate:
            self._transmitting = True
            self._transmitStartTime = TIME()
            return

        if self._transmitting == False:
            return

        # Send the data to the medium and clean up
        self._transmitting = False
        bytelen=int(((TIME()-self._transmitStartTime)*self._dataRate + 0.05)/8)
        # Chop of data if the transmission was terminated prematurely
        bitstream = self._transmittedData[0:bytelen]
        self._niu.medium.completeTransmission(self._niu, bitstream)
        self._transmittedData = None
        self._transmitStartTime = None

        # If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.dl.channelIdle()

    def send(self, bitstream):
        """Accept a block of data and simulate transmission on the medium.

        Called by the MAC layer to transmit a block of data. Can be called
        multiple times while Phy.transmitting is active. In this case, if the
        previous block has not yet been completely transmitted onto the medium,
        the remaining data is discarded and the transmission continues with the
        new data. Therefore, the MAC should call this method only after having
        received a MAC.transmissionCompleted notification or if a collision
        has been detected and the MAC wants to stop the transmission of data
        and continue with a jam signal.

        Arguments:
          bitstream:Bitstream -- Block of data to transmit onto the medium.
        Return value: None.
        """
        if self._transmitting == False:
            raise RuntimeError("Attempt to transmit without previously "
                               "activating transmission on NIU: "
                               + self._niu._host.hostname + "."
                               + self._niu.devicename + ".phy")
        if self._transmittedData == None:
            # New transmission
            self._transmittedData = bitstream
            self._transmitStartTime = TIME()
            self._niu.medium.startTransmission(self._niu)

            transmissionDelay = len(bitstream)*8 / self._dataRate
            self._completeTxEventId = SCHEDULE(transmissionDelay,
                                               self._completeTransmission)

        else:
            # Interrupt current transmission and send new data
            bytelen=int(((TIME()-self._transmitStartTime)*self._dataRate+0.05)/8)
            self._transmittedData = self._transmittedData[0:bytelen]+bitstream
            CANCEL(self._completeTxEventId)
            transmissionDelay = len(bitstream)*8 / self._dataRate
            self._completeTxEventId = SCHEDULE(transmissionDelay,
                                               self._completeTransmission)

    def bittime(self):
        """Return the time it takes to transmit a bit."""
        return 1.0 / self._dataRate

    def _completeTransmission(self):
        """Inform the MAC that PHY has finished transmitting the data.

        The MAC will then call phy.send to continue the transmission
        or phy.transmitting(False) to end the transmission.
        """
        self._niu.dl.sendStatus(0, self._transmittedData)


class AlohaDL(PointToPointDL):
    """Data link layer entity that implements the Aloha protocol.

    Aloha is a simple access control protocol over a shared wireless channel.
    When the sender has to transmit a packet, it does not perform a carrier
    sense to see whether the channel is idle. Instead it immediately transmits
    the packet. It then waits for an acknowledgement. If the acknowledgement
    does not arrive within a given timeout, the packet is resent after a
    backoff. The backoff may be fix or exponential. The retransmission
    strategy is Stop-and-Go.

    It manages an infinite buffer to store the packets received
    from the upper layer but not yet transmitted.
    """
    # Some constants
    FIRSTTR = 3 # Inicates an initial transmission of a frame
    RETR = 2 # Indicates a retransmission
    ACK = 1 # Indicates and acknowledgement

    # State variables for packet transmissions
    _newFrame = None
    """Function that returns a new data frame instance."""
    _outstandingFrame = None
    """Frame which has been transmitted but not yet acknowledged."""
    _transmitting = False
    """State variable to indicate if a packet is being transmitted."""
    _transmitQueue = None
    """List of the frames that have to be transmitted when the link is free."""
    _dstAddress = None
    """Default destination address of a frame."""
    _srcAddress = None
    """Own address"""

    # Sequence numbers
    _VS = None
    """Dict: Addr --> Sequence number of the next new frame to send."""
    _VR = None
    """Dict: Addr --> Next sequence number that is expected to be received."""

    # Backoff
    _retransmissionTimer = None
    """Timer that can be cancelled if the ack is received."""
    retransmissionTimeout = 0.1
    """Timout (default=0.1s) to retransmit if ack has not been received."""
    _slotTime = 0.0
    """The backoff is computed as a multiple of the slotTime."""
    _maxSlots = 1024
    """Maximum number of slot times that a backoff may last."""
    _consecutiveCollisions = 0

    # Statistics
    packetsSent = 0
    """Total number of data packets sent (not acknowledgements)."""
    packetRetransmissions = 0
    """Total number of retransmissions."""
    crcErrors = 0
    """Number of CRC errors in received data frames."""
    sequenceErrors = 0
    """Number of sequence number errors in received frames."""
    packetsReceivedOK = 0
    """Total number of packets that have been received without errors."""

    def __init__(self):
        PointToPointDL.__init__(self)
        self._newFrame = formatFactory(
            [('DstAddr', 'Int', 8, 0), # Destination address
             ('SrcAddr', 'Int', 8, 0), # Source address
             ('SN', 'BitField', 1, 0), # Sequence number: 1 bit, defaul: 0
             ('RN', 'BitField', 1, 0), # Acknowledged SN: 1 bit, default: 0
             ('pad', 'BitField', 6, 0), # Padding to align to octet boundaries
             ('data', 'ByteField', None, None), # Payload
             ('FCS', 'Int', 32, None)], # Checksum: CRC32.
            self)
        self._transmitQueue = [] # List of frames to transmit
        self._computeBackoff = self._fixedBackoff
        self._VR = {}
        self._VS = {}

    def setSrcAddress(self, address):
        """Set the MAC address of the entity.

        The address must be an integer between 1 and 254.
        """
        assert(type(address) == int and 0<=address<=254)
        self._srcAddress = address

    def setDstAddress(self, address):
        """Set the default destination MAC address for packets.

        The address must be an integer between 0 and 254.
        """
        assert(type(address) == int and 0<=address<25)
        self._dstAddress = address
        self._VS[address] = self._VR[address] = 0
        
    def setBackoffModel(self,model="fix",slottime=None, maxSlots=1024):
        """Set the backoff algorithm for retransmissions.

        Before retransmitting a frame, a random time has to be waited.
        The available backoff algorithms are:
          - fix: Compute a random integer k between 0 and maxSlots. The backoff
                 time is k * slottime.
          - exponential: Initially, kmax is 1. Compute a random integer k
                         between 0 and kmax. The backoff time is k * slottime.
                         kmax doubles for each consecutive collision up to
                         a maximum of maxSlots.
        Parameters:
          model:String -- Either 'fix' or 'exponential'
          slottime:Float -- Slot time of the backoff algorithm
          maxSlots:Integer -- Maximum number of slots that a backoff may last.
        """
        assert(model in ["fix", "exponential"])
        if not slottime:
            self._slottime = 1024.0 / self._device.phy.getDataRate()
        else:
            assert(type(slottime) == float and slottime>0)
            self._slottime = slottime
        if model == "fix":
            self._computeBackoff = self._fixedBackoff
        elif model == "exponential":
            self._computeBackoff = self._exponentialBackoff
        self._maxSlots = maxSlots

    # ------------------------------------------------------------------------
    # Send functions

    def send(self,bitstream):
        """Append the packet to the transmit queue and try to send it."""
        if len(self._transmitQueue) > 1000:
               return -1
        if len(bitstream) > 10000:
            print "too long"
            return -1
        self._transmitQueue.append((self.FIRSTTR, self._dstAddress, bitstream))
        self._trySendingFrame()
        return 0

    def _trySendingFrame(self):
        """Send the next frame waiting in the transmitQ, if there is any."""
        if self._transmitting or self._outstandingFrame:
            # Another frame is currently being transmitted. Wait for next call.
            return
        if not self._transmitQueue:
            # Nothing to transmit.
            return

        type,dstAddr,bitstream= self._transmitQueue.pop(0)
        if type == self.ACK:
            # Create a new Ack frame and send it.
            ACTIVITY_INDICATION(self, "tx", "ACK/NAK", "grey", 0, 0)
            self._phySendFrame(dstAddr=dstAddr, data="")
        else:
            if type == self.RETR:
                self.packetRetransmissions += 1
                ACTIVITY_INDICATION(self, "tx", "Resend", "orange", 0, 0)
            else:
                ACTIVITY_INDICATION(self, "tx", "Send", "yellow", 0, 0)
                self._resetBackoff()
                self.packetsSent += 1
            self._retransmissionTimer = SCHEDULE(self.retransmissionTimeout,
                                                 self._timeout)
            self._outstandingFrame = self._phySendFrame(dstAddr,bitstream)
                
    def sendStatus(self,status,bitstream):
        """Called by the phy layer when a transmission is completed.
        """
        assert(status == 0) # Make sure the packet has been sent correctly
        ACTIVITY_INDICATION(self, "tx")
        self._device.phy.transmitting(False)
        self._transmitting = False
        self._trySendingFrame()

    def _phySendFrame(self,dstAddr,data):
        """Fill a new frame and send it to the phy layer."""
        # Create a new frame with CRC and sequence numbers.
        frame = self._newFrame()
        frame.SrcAddr = self._srcAddress
        frame.DstAddr = dstAddr
        frame.SN = self._VS.get(dstAddr,0)
        frame.RN = self._VR.get(dstAddr,0)
        frame.data = data
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        frame.FCS = checksum
        self._transmitting = True
        self._device.phy.transmitting(True)
        self._device.phy.send(frame.serialize())
        return frame

    def channelIdle(self):
        """Called by the Phy if the channel becomes idle. Ignore in Aloha."""
        pass

    # ------------------------------------------------------------------------
    # Receive functions

    def receive(self,bitstream):
        """Receive a frame from the phy layer.

        The frame can contain payload data and/or and acknowledgement.
        """
        # Parse the bit stream, fill it into a PDU and test the CRC
        if ord(bitstream[0]) != self._srcAddress:
            # This is dirty but fast!
            return
        
        frame = self._newFrame()
        frame.fill(bitstream)
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        if frame.FCS != checksum:
            # CRC ERROR. Discard the packet and do nothing.
            ACTIVITY_INDICATION(self, "rx", "CRC error")
            self.crcErrors += 1
            return
        if frame.DstAddr != self._srcAddress:
            # Frame is not for me. Ignore it.
            return
        self._checkAck(frame)
        self._checkData(frame)
        
    def _checkAck(self, frame):
        """Look if the frame contains an ACK and handle it."""
        if self._outstandingFrame != None: # We are waiting for an ACK
            if frame.RN == (self._VS[frame.SrcAddr] + 1) % 2:
                # POSITIVE ACKNOWLEDGEMENT
                ACTIVITY_INDICATION(self, "rx", "ACK ok")
                self._outstandingFrame = None
                if self._retransmissionTimer:
                    CANCEL(self._retransmissionTimer)
                self._retransmissionTimer = None
                self._VS[frame.SrcAddr] = frame.RN
                self._trySendingFrame()

    def _checkData(self,frame):
        """Look if the frame contains payload data and handle it."""
        if len(frame.data) != 0:
            if frame.SN == self._VR.get(frame.SrcAddr,0):
                # Frame contains the next expected SN
                ACTIVITY_INDICATION(self, "rx", "Data OK")
                self.packetsReceivedOK += 1
                # Sent an acknowledgement
                self._VR[frame.SrcAddr] = (frame.SN + 1) % 2
                self._sendACK(frame.SrcAddr)
                # Pass it to the upper layer
                for upperLayer in self._upperLayers:
                    upperLayer.receive(frame.data)
            else:
                # Frame contains a wrong sequence number. Resent last ack.
                ACTIVITY_INDICATION(self, "rx", "Wrong SN")
                self.sequenceErrors += 1
                self._sendACK(frame.SrcAddr)

    def _sendACK(self,dstAddr):
        """Try to send an acknowledgement with the next RN to be received."""
        self._transmitQueue.append((self.ACK, dstAddr, ""))
        self._trySendingFrame()
    
    #-------------------------------------------------------------------------
    # Retransmission functions

    def _timeout(self):
        """Called when a retransmission timeout occurs."""
        ACTIVITY_INDICATION(self, "tx", "TIMEOUT")
        self._retransmissionTimer = None
        self._consecutiveCollisions += 1
        SCHEDULE(self._computeBackoff(), self._retransmit)

    def _retransmit(self):
        """Add the outstanding frame to the transmit queue and try to send it.
        """
        self._retransmissionTimer = None
        self._transmitQueue.append((self.RETR, self._outstandingFrame.DstAddr,
                                    self._outstandingFrame.data))
        self._outstandingFrame = None
        self._trySendingFrame()

    def _computeBackoff(self):
        """Compute a random time to wait before a retransmission."""
        pass

    def _fixedBackoff(self):
        return randint(0,self._maxSlots) * self._slottime

    def _exponentialBackoff(self):
        kmax = min(self._maxSlots, 2**self._consecutiveCollisions - 1)
        return randint(0,kmax) * self._slottime

    def _resetBackoff(self):
        self._consecutiveCollisions = 0


class CSMADL(AlohaDL):
    """Data link layer entity that implements a persistent CSMA MAC.

    A transmission is only started if on carrier is sensed on the channel.
    Otherwise it is deferred until the channel becomes idle.
    """
    def _trySendingFrame(self):
        """Only send if no carrier is sensed."""

        if self._device.phy.carrierSense():
            # Channel is occupied.
            return

        # If channel is idle, send as in normal Aloha
        AlohaDL._trySendingFrame(self)

    def channelIdle(self):
        """Called by the Phy if the channel becomes idle.

        Try to send waiting packet if there are any.
        """
        self._trySendingFrame()

class CSMA_CA_DL(AlohaDL):
    """CSMA with collision avoidance.

    Wait a backoff time
    - after a collision, as in Aloha and CSMA
    - after a successful transmission
    - when the channel is found occupied at a carrier sense before a
      transmission.
    In the first two cases, the backoff is between 0 and 7 timeslots. After
    a collision, the normal backoff algorithm (exponential or fix) is used.
    In contrast to CSMA/CA used in 802.11 wireless LAN, the backoff is
    decremented even when the channel is not idle. This is to facilitate
    the implementation.
    """
    
    _backingOff = False

    def _checkAck(self, frame):
        """Look if the frame contains an ACK and handle it."""
        if self._outstandingFrame != None: # We are waiting for an ACK
            if frame.RN == (self._VS[frame.SrcAddr] + 1) % 2:
                # POSITIVE ACKNOWLEDGEMENT
                ACTIVITY_INDICATION(self, "rx", "ACK ok")
                self._outstandingFrame = None
                if self._retransmissionTimer:
                    CANCEL(self._retransmissionTimer)
                self._retransmissionTimer = None
                self._VS[frame.SrcAddr] = frame.RN

                # Do a backoff. *** COLLISION AVOIDANCE ***
                self._backingOff = True
                SCHEDULE(self._computeBackoff(), self._endBackoff)
                ACTIVITY_INDICATION(self, "tx", "CA backoff", "darkblue", 1,2)

    def _trySendingFrame(self):
        """Only send if no carrier is sensed and we are not in backoff."""
        if self._transmitting or self._outstandingFrame:
            # Another frame is currently being transmitted. Wait for next call.
            return
        if not self._transmitQueue:
            # Nothing to transmit.
            return
        if self._backingOff:
            # Still waiting backoff
            return

        if self._device.phy.carrierSense():
            # Channel is occupied. Do backoff. *** COLLISION AVOIDANCE ***
            self._backingOff = True
            SCHEDULE(self._computeBackoff(), self._endBackoff)
            ACTIVITY_INDICATION(self, "tx", "CA backoff", "darkblue", 1,2)
            return

        type,dstAddr,bitstream= self._transmitQueue.pop(0)
        if type == self.ACK:
            # Create a new Ack frame and send it.
            ACTIVITY_INDICATION(self, "tx", "ACK/NAK", "grey", 0, 0)
            self._phySendFrame(dstAddr=dstAddr, data="")
        else:
            if type == self.RETR:
                self.packetRetransmissions += 1
                ACTIVITY_INDICATION(self, "tx", "Resend", "orange", 0, 0)
            else:
                ACTIVITY_INDICATION(self, "tx", "Send", "yellow", 0, 0)
                self._resetBackoff()
                self.packetsSent += 1
            self._retransmissionTimer = SCHEDULE(self.retransmissionTimeout,
                                                 self._timeout)
            self._outstandingFrame = self._phySendFrame(dstAddr,bitstream)

    #-------------------------------------------------------------------------
    # Retransmission functions

    def _timeout(self):
        """Called when a retransmission timeout occurs."""
        ACTIVITY_INDICATION(self, "tx", "TIMEOUT")
        self._retransmissionTimer = None
        self._consecutiveCollisions += 1
        self._backingOff = True
        ACTIVITY_INDICATION(self, "tx", "Retr backoff", "blue", 1,2)
        SCHEDULE(self._computeBackoff(), self._endBackoff)

    def _retransmit(self):
        """Add the outstanding frame to the transmit queue and try to send it.
        """
        self._retransmissionTimer = None
        self._transmitQueue.append((self.RETR, self._outstandingFrame.DstAddr,
                                    self._outstandingFrame.data))
        self._outstandingFrame = None
        self._trySendingFrame()
    
    #-------------------------------------------------------------------------
    # Backoff functions

    def _exponentialBackoff(self):
        if self._consecutiveCollisions == 0:
            kmax = 8
        else:
            kmax = min(self._maxSlots, 2**self._consecutiveCollisions - 1)
        return randint(0,kmax) * self._slottime

    def _endBackoff(self):
        """Called at the end of a backoff, either because of a collision
        or for collision avoidance.
        """
        ACTIVITY_INDICATION(self, "tx")
        self._backingOff = False
        if self._outstandingFrame:
            # There is an outstanding frame. The backoff was therefore because
            # of a collision of this frame and we have to retransmit this
            # frame
            self._retransmit()
        else:
            # The backoff was because of collision avoidance, either
            # because the channel was found occupied or after a successful
            # transmission. See if we can transmit the next frame.
            self._trySendingFrame()
    
    
    

    
        



    
    
