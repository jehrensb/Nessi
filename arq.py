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

# To do
# -----
# The Stop-and-Wait ARQ is simplex. Bidirectional transmissions interfere with
# acknowledgement transmissions and are not handled correctly.
# The SelectiveRepeatDL is not correct. Find a good description of the
# exact algorithm and implement it.

"""
Data link layer protocols with retransmission strategies.
The implemented ARQ strategies are
  - Stop-and-go
  - Go-back-n (sliding window protocol)
  - Selective repeat request.
All DLC protocols use a CRC32 checksum to test if a frame is correct.
"""

__all__ = ["StopAndGoDL", "GoBackNDL", "SelectiveRepeatDL"]

from simulator import SCHEDULE, CANCEL, ACTIVITY_INDICATION, TIME
from dlc import PointToPointDL
from pdu import PDU, formatFactory
from zlib import crc32
from math import log, ceil
import bisect

class StopAndGoDL(PointToPointDL):
    """Point to point data link layer with Stop-and-go ARQ."""

    retransmissionTimeout = 0.1
    """Timout (default=0.1s) to retransmit if ack has not been received."""

    _retransmissionTimer = None
    """Timer that can be cancelled if the ack is received."""

    _sendBuffer = None
    """Last packet that has been sent but not yet acknowledged."""

    _VS = 0
    """Sequence number of the next new frame to send."""
    _VR = 0
    """Next sequence number that is expected to be received."""

    _newFrame = None
    """Function that returns a new data frame instance."""

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
            [('SN', 'BitField', 1, 0), # Sequence number: 1 bit, defaul: 0
             ('RN', 'BitField', 1, 0), # Acknowledged SN: 1 bit, default: 0
             ('pad', 'BitField', 6, 0), # Padding to align to octet boundaries
             ('data', 'ByteField', None, None), # Payload
             ('FCS', 'Int', 32, None)], # Checksum: CRC32.
            self)
    
    #-------------------------------------------------------------------------
    # Send functions

    def send(self,bitstream):
        """Encapsulate the data into a frame and send it to the phy layer.

        May only be called if self._device.XOFF is False, i.e. if the
        device is ready to accept a new data packet from the higher layer.
        """
        
        # Make sure there is no other packet already in transit.
        assert (self._device.XOFF == False and not self._sendBuffer)

        # Block any new transmission until this packet has been acknowledged
        self._device.XOFF = True

        # Create a new frame with CRC and sequence numbers.
        frame = self._newFrame()
        frame.SN = self._VS ; self._VS = (self._VS + 1) % 2
        frame.RN = self._VR
        frame.data = bitstream
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        frame.FCS = checksum

        # Set the retransmission timer  
        self._sendBuffer = frame
        self._retransmissionTimer = SCHEDULE(self.retransmissionTimeout,
                                             self._timeout)

        # Sent the frame
        ACTIVITY_INDICATION(self, "tx", "Send", "yellow", 0, 0)
        self.packetsSent += 1
        self._device.phy.send(frame.serialize())
        return 0

    def sendStatus(self,status,bitstream):
        """Called by the phy layer when a transmission is completed.
        """
        assert(status == 0) # Make sure the packet has been sent correctly
        ACTIVITY_INDICATION(self, "tx")

    def _sendACK(self):
        """Send an acknowledgement with the next RN to be received."""
        # Create a new frame with CRC and sequence numbers.
        ack = self._newFrame()
        ack.SN = self._VS 
        ack.RN = self._VR # This decides whether it is an ACK or a NAK
        checksum = crc32(ack.serialize()[:-4]) & ((1L<<32)-1)
        ack.FCS = checksum

        # Sent the acknowledgement
        ACTIVITY_INDICATION(self, "tx", "ACK/NAK", "grey", 0, 0)
        self._device.phy.send(ack.serialize())

    #-------------------------------------------------------------------------
    # Receive functions

    def receive(self,bitstream):
        """Receive a frame from the phy layer.

        The frame can contain payload data and/or and acknowledgement.
        """
        # Parse the bit stream, fill it into a PDU and test the CRC
        frame = self._newFrame()
        frame.fill(bitstream)
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        if frame.FCS != checksum:
            # CRC ERROR. Discard the packet and do nothing.
            ACTIVITY_INDICATION(self, "rx", "CRC error")
            self.crcErrors += 1
            return

        self._checkAck(frame)
        self._checkData(frame)
        
    def _checkAck(self, frame):
        """Look if the frame contains an ACK and handle it."""
        if self._sendBuffer != None: # We are waiting for an ACK
            if frame.RN == self._VS:
                # POSITIVE ACKNOWLEDGEMENT
                ACTIVITY_INDICATION(self, "rx", "ACK")
                bitstream = self._sendBuffer.data
                self._sendBuffer = None
                CANCEL(self._retransmissionTimer)
                self._retransmissionTimer = None
                self._device.XOFF = False # Allow the next packet to be sent
                # Inform the upper layer that it can sent the next packet
                # @@@ FIXME: this is not clean. Better provide a queuing layer
                for upperLayer in self._upperLayers:
                    upperLayer.sendStatus(0,bitstream)
            else:
                # NEGATIVE ACKNOWLEDGEMENT. Retransmit the packet.
                ACTIVITY_INDICATION(self, "rx", "NAK")
                self._retransmit()

    def _checkData(self,frame):
        """Look if the frame contains payload data and handle it."""
        if len(frame.data) != 0:
            if frame.SN == self._VR:
                # Frame contains the next expected SN
                ACTIVITY_INDICATION(self, "rx", "Data OK")
                self.packetsReceivedOK += 1
                # Sent an acknowledgement
                self._VR = (self._VR + 1) % 2
                self._sendACK()
                # Pass it to the upper layer
                for upperLayer in self._upperLayers:
                    upperLayer.receive(frame.data)
            else:
                # Frame contains a wrong sequence number. Request missing pkt.
                ACTIVITY_INDICATION(self, "rx", "Wrong SN")
                print "Sequence error"
                self.sequenceErrors += 1
                self._sendACK()

    #-------------------------------------------------------------------------
    # Retransmission functions

    def _timeout(self):
        """Called when a retransmission timeout occurs."""
        ACTIVITY_INDICATION(self, "tx", "TIMEOUT")
        self._retransmissionTimer = None
        self._retransmit()

    def _retransmit(self):
        """Retransmits the current frame.

        Called either because of a negative ack or by a retransmission timeout.
        """
        ACTIVITY_INDICATION(self, "tx", "Retransmit", "orange", 0, 0)
        if self._retransmissionTimer:
            CANCEL(self._retransmissionTimer)
        self._retransmissionTimer=SCHEDULE(self.retransmissionTimeout,
                                           self._timeout)
        self.packetRetransmissions += 1
        self.packetsSent += 1
        self._device.phy.send(self._sendBuffer.serialize())


class GoBackNDL(StopAndGoDL):
    """Point to point data link layer with Go-back-n (sliding window) ARQ.

    The algoritm follows Bertsekas/Gallager, 'Data Networks', 2nd edition 1992,
    p. 80.
    The sliding window is controlled by two variables:
    - SNmin is the smallest sequence number not yet acknowledged. It is the
      left window end.
    - SNmax is the next sequence number to be used for a new paquet from
      the upper layer.
    New packets are only accepted from the higher layer if the number of
    waiting packets is smaller than the window size.

    Besides the sending window, a transmission queue is managed that contains
    that packets that have to be sent. This helps to conveniently manage
    retransmissions.
    """
    FIRSTTR = 3 # Inicates an initial transmission of a frame
    RETR = 2 # Indicates a retransmission
    ACK = 1 # Indicates and acknowledgement

    _SN_MOD = 65536
    """Modulus for SN."""
    _winSize = 0
    """Size of the sliding window, measured in packets."""
    _SNmin = 0
    """Smallest sequence number not yet acknowledged. Left window end."""
    _SNmax = 0
    """Next free sequence to be used for a new packet."""
    _sendBuffer = None
    """Dictionary: SN --> bitstream. Contains the packets of the window."""

    _retransmissionTimer = None
    """Dictionary: SN --> Timer. Used to cancel scheduled timeouts."""

    _transmitting = False
    """State variable to indicate if a packet is being transmitted."""
    _transmitQueue = None
    """List of the frames that have to be transmitted when the link is free."""

    def __init__(self,numSNBits=16):
        """Initialize the packet format. By default use 16 bits for seq.nums.

        Arguments:
          numSNBits:Integer -- number of bits for the sequence numbers in
                               the packet format.
        """
        PointToPointDL.__init__(self)
        self._newFrame = None # We need the window size before creating PDUs.
        self._sendBuffer = {} # Dictionary: SN --> Bitstream
        self._retransmissionTimer = {} # Dictionary: SN --> Timer
        self._transmitQueue = [] # List of frames to transmit

        self._SN_MODULO = 2**numSNBits
        if (2*numSNBits) % 8 != 0:
            padLen = 8 - (2*numSNBits)%8
            self._newFrame = formatFactory(
                [('SN', 'BitField', numSNBits, 0), # Sequence number
                 ('RN', 'BitField', numSNBits, 0), # Acknowledged SN
                 ('pad', 'BitField', padLen, 0), # Padding to align to octets
                 ('data', 'ByteField', None, None), # Payload
                 ('FCS', 'Int', 32, None)], # Checksum: CRC32.
                self)
        else:
            self._newFrame = formatFactory(
                [('SN', 'BitField', numSNBits, 0), # Sequence number
                 ('RN', 'BitField', numSNBits, 0), # Acknowledged SN
                 ('data', 'ByteField', None, None), # Payload
                 ('FCS', 'Int', 32, None)], # Checksum: CRC32.
                self)

    def setWindowSize(self, numPackets):
        """Sets the size of the sliding window, measured in paquets."""
        numPackets = int(numPackets)
        assert(numPackets >= 0)
        self._winSize = numPackets

    #-------------------------------------------------------------------------
    # Send functions

    def send(self, bitstream):
        """Place the new packet into the sliding window.

        May only be called if self._device.XOFF is False, i.e. if the
        device is ready to accept a new data packet from the higher layer.
        """
        # Make sure we can accept a new frame
        assert(self._device.XOFF == False)

        # Place the frame into the window and the transmit queue
        self._sendBuffer[self._SNmax] = bitstream
        bisect.insort(self._transmitQueue, (self.FIRSTTR,self._SNmax))
        self._SNmax = (self._SNmax + 1) % self._SN_MOD

        # If the window is full, do not accept any new frames from upper layer
        if (self._SNmax - self._SNmin) % self._SN_MOD >= self._winSize:
            self._device.XOFF = True

        self._trySendingFrame()
        return 0

    def _trySendingFrame(self):
        """Send the next frame waiting in the sendBuffer, if there is any."""
        if self._transmitting:
            # Another frame is currently being transmitted. Wait for next call.
            return
        if not self._transmitQueue:
            # Nothing to transmit.
            return
        
        type,sn = self._transmitQueue.pop(0)
        if type == self.ACK:
            # Create a new Ack frame and send it.
            ack = self._newFrame()
            ack.SN = self._SNmax # Allowed since payload is empty
            ack.RN = sn
            checksum = crc32(ack.serialize()[:-4]) & ((1L<<32)-1)
            ack.FCS = checksum
            ACTIVITY_INDICATION(self, "tx", "Send ACK RN=%s"%str(ack.RN),
                                "grey", 0, 0)
            self._transmitting = True
            self._device.phy.send(ack.serialize())
        else:
            assert(type == self.FIRSTTR or type == self.RETR)
            # Create a new data packet and send it
            bitstream = self._sendBuffer[sn]
            frame = self._newFrame()
            frame.SN = sn
            frame.RN = self._VR
            frame.data = bitstream
            checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
            frame.FCS = checksum

            # Set the retransmission timer  
            self._retransmissionTimer[sn]=SCHEDULE(self.retransmissionTimeout,
                                                   self._timeout, (sn,))
            
            # Send the frame and update the statistics
            if type == self.RETR:
                self.packetRetransmissions += 1
                ACTIVITY_INDICATION(self, "tx", "Retr SN=%s"%str(frame.SN),
                                    "orange", 0, 0)
                
            else:
                ACTIVITY_INDICATION(self, "tx", "Send SN=%s"%str(frame.SN),
                                    "yellow", 0, 0)
            self.packetsSent += 1
            self._transmitting = True
            self._device.phy.send(frame.serialize())
        
    def sendStatus(self,status,bitstream):
        """Called by the phy layer when a transmission is completed.
        """
        assert(status == 0) # Make sure the packet has been sent correctly
        ACTIVITY_INDICATION(self, "tx")
        self._transmitting = False

        # See if there are another frame waiting for transmission
        self._trySendingFrame()
        
    #-------------------------------------------------------------------------
    # Receive functions

    def receive(self,bitstream):
        """Receive a frame from the phy layer.

        The frame can contain payload data and/or and acknowledgement.
        """
        # Parse the bit stream, fill it into a PDU and test the CRC
        frame = self._newFrame()
        frame.fill(bitstream)
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        if frame.FCS != checksum:
            # CRC ERROR. Discard the packet and do nothing.
            ACTIVITY_INDICATION(self, "rx", "CRC error")
            self.crcErrors += 1
            return

        self._checkAck(frame)
        self._checkData(frame)
        
    def _checkAck(self, frame):
        """Look if the frame contains an ACK and handle it."""
        RN = frame.RN

        # Test if the RN is inside the window
        if self._SNmin == self._SNmax:
            # We do not expect a new ack.
            return
    
        if ( (RN - self._SNmin) % self._SN_MOD
             > (self._SNmax - self._SNmin) % self._SN_MOD ):
            # ACK outside window. Do nothing
            ACTIVITY_INDICATION(self, "rx", "DupACK RN=%s"%str(RN))
            return

        # RN is inside the window and acknowledges all frames before RN.
        # Remove the acknowledged frames from the window, transmission
        # queue and cancel the timers.
        ACTIVITY_INDICATION(self, "rx", "Rcv ACK RN=%s"%str(RN))
        while self._SNmin != RN:
            assert((self.FIRSTTR,self._SNmin) not in self._transmitQueue)
            if (self.RETR,self._SNmin) in self._transmitQueue: 
                self._transmitQueue.remove((self.RETR,self._SNmin))
            bitstream = self._sendBuffer.pop(self._SNmin)
            timer = self._retransmissionTimer.pop(self._SNmin,None)
            if timer:
                CANCEL(timer)
            # Move the left window edge and see if we can accept new frames.
            self._SNmin = (self._SNmin+1) % self._SN_MOD
            if (self._SNmax - self._SNmin) % self._SN_MOD < self._winSize:
                self._device.XOFF = False
                
            # Inform the upper layer that it can sent the next packet
            # @@@ FIXME: this is not clean. Better provide a queue
            for upperLayer in self._upperLayers:
                upperLayer.sendStatus(0,bitstream)

    def _checkData(self,frame):
        """Look if the frame contains payload data and handle it."""
        if len(frame.data) != 0:
            if frame.SN == self._VR:
                # Frame contains the next expected SN
                ACTIVITY_INDICATION(self, "rx", "Rcv OK SN=%s"%str(frame.SN))
                self.packetsReceivedOK += 1
                # Sent an acknowledgement
                self._VR = (self._VR + 1) % self._SN_MOD
                self._sendACK()
                # Pass it to the upper layer
                for upperLayer in self._upperLayers:
                    upperLayer.receive(frame.data)
            else:
                # Frame contains a wrong sequence number. Request missing pkt.
                ACTIVITY_INDICATION(self, "rx",
                                    "Rcv wrong SN=%s"%str(frame.SN))
                self.sequenceErrors += 1
                self._sendACK()

    def _sendACK(self):
        """Try to send an acknowledgement with the next RN to be received."""
        bisect.insort(self._transmitQueue, (self.ACK,self._VR))
        self._trySendingFrame()
    
    #-------------------------------------------------------------------------
    # Retransmission functions

    def _timeout(self,sn):
        """Called when a retransmission timeout occurs."""

        ACTIVITY_INDICATION(self, "tx", "TIMEOUT SN=%s"%str(sn))
        del self._retransmissionTimer[sn]
        self._retransmit(sn)

    def _retransmit(self,sn):
        """Cancel all waiting frame transmissions and resent the whole window.
        """
        # Only keep waiting acknowledgements in the transmit queue.
        self._transmitQueue = [el for el in self._transmitQueue
                               if el[0] == self.ACK]
        for timer in self._retransmissionTimer.values():
            CANCEL(timer)
        self._retransmissionTimer = {}

        # Place the whole window into the transmission queue
        for sn in self._sendBuffer.keys():
            bisect.insort(self._transmitQueue, (self.RETR, sn))
        self._trySendingFrame()


class SelectiveRepeatDL(GoBackNDL):

    FIRSTTR = 3 # Inicates an initial transmission of a frame
    RETR = 2 # Indicates a retransmission
    ACK = 1 # Indicates and acknowledgement
    SREJ = 0 # Indicates a selective repeat request

    _receiveBuffer = 0
    """Dictionary: SN --> Received data. Contains the data not yet delivered
    to the upper layer."""

    def __init__(self,numSNBits=16):
        GoBackNDL.__init__(self,numSNBits)
        self._receiveBuffer = {} # Dictionary: SN --> Bitstream

        self._SN_MODULO = 2**numSNBits
        if (2*numSNBits) % 8 != 0:
            padLen = 8 - (2*numSNBits)%8
            self._newFrame = formatFactory(
                [('SN', 'BitField', numSNBits, 0), # Sequence number
                 ('RN', 'BitField', numSNBits, 0), # Acknowledged SN
                 ('SREJ', 'Int', 8, 0), # 1 byte to signal SREJ
                 ('pad', 'BitField', padLen, 0), # Padding to align to octets
                 ('data', 'ByteField', None, None), # Payload
                 ('FCS', 'Int', 32, None)], # Checksum: CRC32.
                self)
        else:
            self._newFrame = formatFactory(
                [('SN', 'BitField', numSNBits, 0), # Sequence number
                 ('RN', 'BitField', numSNBits, 0), # Acknowledged SN
                 ('SREJ', 'Int', 8, 0), # 1 byte to signal SREJ
                 ('data', 'ByteField', None, None), # Payload
                 ('FCS', 'Int', 32, None)], # Checksum: CRC32.
                self)

    #-------------------------------------------------------------------------
    # Send functions
    # Inherited from GoBackNDL:
    # - send
    # - sendStatus

    def _trySendingFrame(self):
        """Send the next frame waiting in the sendBuffer, if there is any."""
        if self._transmitting:
            # Another frame is currently being transmitted. Wait for next call.
            return
        if not self._transmitQueue:
            # Nothing to transmit.
            return
        
        type,sn = self._transmitQueue.pop(0)
        if type == self.ACK or type == self.SREJ:
            # Create a new Ack frame and send it.
            ack = self._newFrame()
            ack.SN = self._SNmax # Allowed since payload is empty
            ack.RN = sn
            if type == self.SREJ:
                ack.SREJ = 1
                ACTIVITY_INDICATION(self, "tx", "Send SREJ RN=%s"%str(ack.RN),
                                    "red", 0, 0)
            else:
                ACTIVITY_INDICATION(self, "tx", "Send ACK RN=%s"%str(ack.RN),
                                    "grey", 0, 0)
            checksum = crc32(ack.serialize()[:-4]) & ((1L<<32)-1)
            ack.FCS = checksum
            self._transmitting = True
            self._device.phy.send(ack.serialize())

        else:
            assert(type == self.FIRSTTR or type == self.RETR)
            # Create a new data packet and send it
            bitstream = self._sendBuffer[sn]
            frame = self._newFrame()
            frame.SN = sn
            frame.RN = self._VR
            frame.data = bitstream
            checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
            frame.FCS = checksum

            # Set the retransmission timer
            if sn in self._retransmissionTimer:
                timer = self._retransmissionTimer.pop(sn)
                CANCEL(timer)
            self._retransmissionTimer[sn]=SCHEDULE(self.retransmissionTimeout,
                                                   self._timeout, (sn,))
            
            # Send the frame and update the statistics
            if type == self.RETR:
                self.packetRetransmissions += 1
                ACTIVITY_INDICATION(self, "tx", "Retr SN=%s"%str(frame.SN),
                                    "orange", 0, 0)
                
            else:
                ACTIVITY_INDICATION(self, "tx", "Send SN=%s"%str(frame.SN),
                                    "yellow", 0, 0)
            self.packetsSent += 1
            self._transmitting = True
            self._device.phy.send(frame.serialize())

    #-------------------------------------------------------------------------
    # Receive functions
    # Inherited from GoBackNDL:
    # - None 

    def receive(self,bitstream):
        """Receive a frame from the phy layer.

        The frame can contain payload data and/or and acknowledgement.
        """
        # Parse the bit stream, fill it into a PDU and test the CRC
        frame = self._newFrame()
        frame.fill(bitstream)
        checksum = crc32(frame.serialize()[:-4]) & ((1L<<32)-1)
        if frame.FCS != checksum:
            # CRC ERROR. Discard the packet and do nothing.
            ACTIVITY_INDICATION(self, "rx", "CRC error")
            self.crcErrors += 1
            
            # Send a SREJ for the first required frame
            self._sendACK(self.SREJ, self._VR)
            return

        self._checkAck(frame)
        self._checkData(frame)
        
    def _checkAck(self, frame):
        """Look if the frame contains an ACK or SREJ and handle it."""

        if self._SNmin == self._SNmax:
            # We do not expect a new ack.
            return
    
        RN = frame.RN
        if frame.SREJ:
            # This is a selective repeat request. Retransmit RN
            # if the window allows it
            if ( (RN - self._SNmin) % self._SN_MOD
                 < (self._SNmax-self._SNmin)%self._SN_MOD ):
                ACTIVITY_INDICATION(self, "rx", "SREJ RN=%s"%str(RN))
                self._retransmit(RN)
                return

        if ( (RN - self._SNmin) % self._SN_MOD
             > (self._SNmax - self._SNmin) % self._SN_MOD ):
            # ACK outside window. Do nothing
            ACTIVITY_INDICATION(self, "rx", "DupACK RN=%s"%str(RN))
            return

        # RN is inside the window. In contrast to Go-back-n, it only
        # acknowledges one packet, not all packets before RN
        ACTIVITY_INDICATION(self, "rx", "Rcv ACK RN=%s"%str(RN))
        bitstream = self._sendBuffer.pop(RN,None)
        if bitstream:
            if (self.RETR,RN) in self._transmitQueue: 
                self._transmitQueue.remove((self.RETR,RN))
            timer = self._retransmissionTimer.pop(RN,None)
            if timer:
                CANCEL(timer)

            # Let's see if we can move the window. Move it up to the first non
            # acknowledged packet.
            while (self._SNmin!=self._SNmax
                   and self._SNmin not in self._sendBuffer):
                assert((self.FIRSTTR,self._SNmin) not in self._transmitQueue)
                # Move the left window edge and see if we can accept new frames
                self._SNmin = (self._SNmin+1) % self._SN_MOD
                if (self._SNmax - self._SNmin) % self._SN_MOD < self._winSize:
                    self._device.XOFF = False

            # Inform the upper layer that it can sent the next packet
            # @@@ FIXME: this is not clean. Better provide a queue
            for upperLayer in self._upperLayers:
                upperLayer.sendStatus(0,bitstream)

    def _checkData(self,frame):
        """Look if the frame contains payload data and handle it."""
        if len(frame.data) != 0:
            # If frame is inside the reception window, then accept it
            if (frame.SN - self._VR) % self._SN_MOD < self._winSize:
                ACTIVITY_INDICATION(self, "rx", "Rcv OK SN=%s"%str(frame.SN))
                self._receiveBuffer[frame.SN] = frame.data

                # If it is the next expected sequence number, then we can
                # pass some data to the upper layers
                bitstream = self._receiveBuffer.pop(self._VR,None)
                while  bitstream != None:
                    for upperLayer in self._upperLayers:
                        upperLayer.receive(bitstream)
                    self._VR = (self._VR + 1) % self._SN_MOD
                    bitstream = self._receiveBuffer.pop(self._VR,None)

                # Send an Ack for _this_ frame
                self._sendACK(self.ACK, frame.SN)
            else:
                # Frame contains a wrong sequence number.
                # If it is and old packet, acknowledge it, otherwise
                # send a SREJ for the first missing packet
                if (self._VR - frame.SN) % self._SN_MOD < self._winSize+1:
                    self._sendACK(self.ACK, frame.SN)
                    ACTIVITY_INDICATION(self, "rx",
                                        "Send old ACK RN=%s"%str(frame.SN))
                else:
                    ACTIVITY_INDICATION(self, "rx",
                                        "Rcv wrong RN=%s"%str(frame.SN))
                    self.sequenceErrors += 1
                    self._sendACK(self.SREJ, self._VR)

    def _sendACK(self, type, rn):
        """Try to send an ACK or SREJ with the given RN.""" 
        bisect.insort(self._transmitQueue, (type,rn))
        self._trySendingFrame()

    #-------------------------------------------------------------------------
    # Retransmission functions
    # Inherited from GoBackNDL
    # - _timeout

    def _retransmit(self,sn):
        """Resent the frame that has timed out."""
        bisect.insort(self._transmitQueue, (self.RETR, sn))
        self._trySendingFrame()
