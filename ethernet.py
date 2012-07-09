# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: June 2003
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

"""Physical, MAC and LLC layer protocol entities for the Ethernet protocol.

The module exports the following classes:
PHY -- Physical layer entity for the Ethernet 802.3 protocol.
MAC -- Medium Access Control sublayer for the Ethernet 802.3 protocol.
LLC -- Link Layer Control sublayer according to 802.2, type 1.

Additionally, the following constants are exported:
HALF_DUPLEX -- Half duplex transmission mode.
FULL_DUPLEX -- Full duplex transmission mode.
"""

__all__ = ["HALF_DUPLEX", "FULL_DUPLEX", "PHY", "MAC"]

from random import random 
from zlib import crc32
from netbase import ProtocolEntity, NIU, Device
from media import Bus
from netbase import PhyLayer, DLBottom, DLTop
from pdu import PDU, formatFactory

from simulator import SCHEDULE, CANCEL, TIME, ACTIVITY_INDICATION, TRACE

HALF_DUPLEX = 0
"""Constant for half duplex mode."""
FULL_DUPLEX = 1
"""Constant for full duplex mode."""

# Internal constants for use between MAC and LLC.
_TRANSMIT_OK = 0
"""Error ode for the upper layer to indicate that the transmission succeeded."""
_EXCESSIVE_COLLISION_ERROR = 1
"""Error code for the upper layer to indicate that the transmission failed."""

_UNKNOWN_TRANSMISSION_ERROR = 2
"""Error code for any other transmission error caused by the PHY."""

class PHY(PhyLayer):
    """Physical layer entity for the Ethernet 802.3 protocol.

    The task of the physical layer is to accept bits from the MAC
    sublayer and to transmit them over the attached medium as well as
    to receive bits from the medium and pass them to the MAC
    sublayer. Additionally, it has to provide information to the MAC
    sublayer if the medium is idle or occupied (=carrier sense) and
    whether a collision is detected during transmission of the MAC data.

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
      - setDuplexMode -- Set the mode to HALF_DUPLEX or FULL_DUPLEX.
      - getDuplexMode -- Return the transmission mode: HALF_DUPLEX or FULL_DUPLEX.
      - setDataRate -- Set the data rate of the physical interface to 10,100, or 1000 Mb/s.
      - getDataRate -- Return the data rate of the physical interface.
    """

    def __init__(self):
        self._dataRate = 10e6
        """Data rate for transmission. In bits/s. Type: float."""
        self._mode = HALF_DUPLEX
        """Transmission mode: _HALF_DUPLEX or _FULL_DUPLEX."""

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

    def setDuplexMode(self, mode):
        """Set the mode to HALF_DUPLEX or FULL_DUPLEX.

        On a bus, only HALF_DUPLEX is possible.

        Arguments:
          mode: HALF_DUPLEX or FULL_DUPLEX.
        Return value: boolean -- True if successful, otherwise False.
        """
        if mode == HALF_DUPLEX:
            self._mode = HALF_DUPLEX
            return True
        if mode == FULL_DUPLEX:
            if isinstance(self._niu.getMedium, Bus):
                return False
            else:
                self._mode = mode
                return True

    def getDuplexMode(self):
        """Return the transmission mode: HALF_DUPLEX or FULL_DUPLEX."""
        return self._mode

    def setDataRate(self, dataRate):
        """Set the data rate of the physical interface to 10,100, or 1000 Mb/s."""
        if dataRate in (10e6, 100e6, 1000e6):
            self._dataRate = dataRate
        else:
            raise ValueError("Invalid data rate on Ethernet NIU "
                             + self._niu._node.hostname + "."
                             + self._niu.devicename
                             + ".phy: " + `dataRate`)
    def getDataRate(self):
        """Return the data rate of the physical interface."""
        return self._dataRate
                
    def newChannelActivity(self):
        """Register a new channel activity and detect collisions.

        Called by the medium when another NIU starts transmitting. The
        method determines if the new transmission causes a receive collision
        (collision with transmissions of other NIUs) or a transmit collision
        (collision with the transmission of the local NIU. Receive collisions
        are remembered to later invalidate the received data before passing
        it to the MAC. A transmit collision is signalled to the MAC as
        collision detect. The MAC layer may choose to ignore the signal in
        full duplex mode.
        """

        self._receiveActivities += 1
        if self._receiveActivities == 1:
            self._receiveStartTime = TIME()
            self._overlappingReceptions = False
        else:
            self._overlappingReceptions = True

        if self._transmitting:
            self._niu.mac.collisionDetect()

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
        bytelen = int(((TIME()-self._receiveStartTime)*self._dataRate + 0.05)/ 8)
        if self._overlappingReceptions:
            self._overlappingReceptions = False
            self._receiveStartTime = None
            bitstream = '\x00' * bytelen
        elif len(bitstream) != bytelen:
            raise ValueError("Speed mismatch on Ethernet NIU "
                             + self._niu._node.hostname + "."
                             + self._niu.devicename
                             + ".phy: received data with invalid length")
        self._niu.mac.receive(bitstream)

        # If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.mac.channelIdle()

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
        bytelen = int(((TIME()-self._transmitStartTime)*self._dataRate + 0.05)/8)
        # Chop of data if the transmission was terminated prematurely
        bitstream = self._transmittedData[0:bytelen]
        self._niu.medium.completeTransmission(self._niu, bitstream)
        self._transmittedData = None
        self._transmitStartTime = None

        # If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.mac.channelIdle()

    def send(self, bitstream):
        """Accept a block of data and simulate transmission on the medium.

        Called by the MAC layer to transmit a block of data. Can be called
        multiple times while Phy.transmitting is active (). In this case, if the
        previous block has not yet been completely transmitted onto the medium,
        the remaining data is discarded and the transmission continues with the
        new data. Therefore, the MAC should call this method only after having
        received a MAC.sendStatus notification or if a collision
        has been detected and the MAC wants to stop the transmission of data
        and continue with a jam signal.

        Arguments:
          bitstream:Bitstream -- Block of data to transmit onto the medium.
        Return value: None.
        """
        if self._transmitting == False:
            raise RuntimeError("Attempt to transmit without previously "
                               "activating transmission on NIU: "
                               + self._niu._node.hostname + "."
                               + self._niu.devicename + ".phy")
        if self._transmittedData == None:
            # New transmission
            self._transmittedData = bitstream
            self._transmitStartTime = TIME()
            self._niu.medium.startTransmission(self._niu)

            transmissionDelay = len(bitstream)*8 / self._dataRate
            self._completeTxEventId = SCHEDULE(transmissionDelay,
                                               self._completeTransmission)

            if self._receiveActivities > 0:
                self._niu.mac.collisionDetect()
        else:
            # Interrupt current transmission and send new data
            bytelen = int(((TIME()-self._transmitStartTime)*self._dataRate + 0.05)/8)
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
        self._niu.mac.sendStatus(0, self._transmittedData)
        
            
class MAC(DLBottom):
    """Medium Access Control sublayer for the Ethernet 802.3 protocol.

    This class implements the MAC sublayer of Ethernet according to the
    standard IEEE Std 802.3(TM)-2002. Both half and full duplex functionality
    is implemented for 10 Mb/s, 100 Mb/s and 1000 Mb/s physical layers.
    The functionality of the MAC sublayer is summarized on page 1 of the
    standard and detailed in the Sections 2 to 4 of the standard. In
    particular, the Section 4.1.2.1 describes the operation of the MAC
    sublayer.

    The service provided by the MAC sublayer allow the upper layer to
    exchange packets with peer entities. The upper layer is the data link
    protocol entity 'dl' of the NIU, which is normally LLC.
    MAC interfaces with dl via the following methods
      - MAC.send -- accept a packet and transmit it over the LAN
      - dl.sendStatus -- indicate the success or failure of a previous send
      - dl.receive -- pass received data to the upper layer

    The send and receive functions are renamed with respect to the standard
    (Section 4.3.2) to be conform with the ProtocolEntity interface of the
    simulator.
    Moreover, the standard specifies that the send and receive operation are
    synchronous and block the caller during the data transmission or reception.
    This cannot be implemented in the simulator.
    For the send functionality, a new method dl.sendStatus is therefore
    introduced that informs the data link layer of the success or failure of a
    previous send call. The dl.receive method is simply implemented as
    a non-blocking function call.

    MAC uses the services offered from the physical layer.
    Interface to the PHY layer:
      - MAC.channelIdle -- Called by PHY when the medium becomes idle.
      - MAC.sendStatus -- Called by PHY when a transmission ends.
      - MAC.collisionDetect -- In half duplex mode, handle a collision.
      - MAC.receive -- Receive a bitstream from the PHY layer, test it and pass it to dl.
      
    This interface is an abstraction of the interface defined in the standard
    (Section 4.3.3). It provides the functionality of the PHY layer to MAC
    but does not intend to match the internal structure of a real PHY layer.
    The differences between the standard and the simulation model are:
      - In the standard, the transmit and receive functions operate bit-wise
        and are synchronous, which is not possible in the simulator.
        The PHY.transmitBit function is therefore implemented as an
        non-blocking method of PHY that transmits entire blocks of data.
        When the transmission onto the medium is completed, PHY informs MAC
        by calling MAC.sendStatus.
        The receiveBit function of the standard is replaced by the
        non-blocking method MAC.receive with an entire frame as argument.
        The ReceiveDataValid variable of the standard hence is not required.
      - The Wait function of the standard blocks the caller for a specified
        number of bit times. This cannot be implemented. It is modeled
        by a method PHY.bittimes that returns the duration of a bit
        and a SCHEDULE call to the simulator for the required delay.
      - According to the standard, MAC has to continuously monitor the
        collisionDetect and carrierSense variables of the PHY layer to detect
        any changes. This unnecessarily complicates the model.
        These functionalities are therefore implemented by upcalls to the MAC
        methods collisionDetect and channelIdle.

    The following functionalities defined in the standard are not implemented:
      - Frame bursting (4.2.3.2.7).

    Configuration interface of MAC:
      - MAC.install -- install the MAC protocol on a NIU.
      - MAC.setAddress -- change the MAC address
x     - MAC.getAddress -- get the current MAC address
      - MAC.addGroupAddress -- Add a multicast address to the address filter
      - MAC.deleteGroupAddress -- Remove a multicast address from the filter.

    """

    # MAC constants. Defined in the standard, Section 4.4.2
    _SLOTTIME = 512
    """Slot time in bits for 10 Mb/s and 100 Mb/s Ethernet."""
    _GIGA_SLOTTIME = 4096
    """Slot time in bits for Gigabit Ethernet."""
    _INTERFRAME_GAP = 96 
    """Interframe gap in bits for 10 Mb/s, 100 Mb/s and 1000 Mb/s Ethernet."""
    _JAMSIZE = 32 / 8
    """Length of jam signal in bytes."""
    _MIN_FRAMESIZE = 512 / 8
    """Minimum frame size in bytes, counting all bytes from destAddr to FCS."""
    _MAX_UNTAGGED_FRAMESIZE = 1518
    """Maximum frame size in bytes, counting all bytes from destAddr to FCS."""

    def __init__(self):
        """Initialize instance variables for internal use and statistics."""
        self.address = None
        """MAC address of the protocol entity."""

        # Private fields
        self._PDU = None
        """PDU class for frames according to the Ethernet frame format."""
        self._addressFilter = ["FF:FF:FF:FF:FF:FF"]
        """List of recognized multicast addresses that the MAC shall receive."""
        self._transmissionAttemps = 0
        """Attempts to transmit a frame."""
        self._jamming = False
        """True, while transmitting jam. Ignore collisions. At end start backoff."""
        self._waitingForIdleChannel = False
        """True, if while a transmission is deferred due to carrierSense."""
        
        self._latestTransmitActivity = 0
        """End time of the latest transmission. Used to compute interframe gap."""
        self._latestReceiveActivity = 0
        """End time of the latest reception. Used to compute interframe gap."""
        
        # Statistics
        self.framesTransmittedOK = 0
        """Count of frames that are successfully transmitted."""
        self.singleCollisionFrames = 0
        """Count of frames that suffered a single collision."""
        self.multipleCollisionFrames = 0
        """Count of successfully transmitted frames with more than 1 collision."""
        self.framesReceivedOK = 0
        """Count of frames that are successfully received."""
        self.frameCheckSequenceErrors = 0
        """Count of received frames that did not pass the FCS check."""
        self.octetsTransmittedOK = 0
        """Count of data and padding octets of successfully transmitted frames."""
        self.octetsReceivedOK = 0
        """Count of data and padding octets of successfully received frames."""
        self.excessiveCollisions = 0
        """Count of aborded frames due to 16 consecutive collisions."""
        self.octetsTransmittedError = 0
        """Count of data octets not sent because of errors."""
        self.lateCollisions = 0
        """Count of times that a collision has been detected later than 512 bit times after the start of the transmission."""
        
    def install(self, niu, protocolName):
        """Install the protocol entity on a NIU.

        This method is called by the node or the NIU to inform the protocol
        that is has been installed. It registers the NIU for later access
        and chooses a random MAC address that can later by changed using the
        MAC.setAddress method. It also creates a new PDU class 802.3 for its
        MAC frames. The format is described in the standard, Section 3.1.1.

        Arguments:
          niu:NIU -- NIU on which self is installed
          protocoleName:String -- Must be 'mac'.
        Return value: None.
        """
        
        if isinstance(niu, NIU):
            self._niu = niu
        else:
            raise TypeError("Ethernet MAC entity must be installed on a NIU")
        if protocolName != "mac":
            raise NameError("Ethernet MAC entity must be installed under the "
                            "name 'mac'")
        self._protocolName = "mac"
        self.fullName = niu.fullName + ".mac"

        ints = [int(random()*256) for i in range(6)]
        if ints[0]%2 == 1:
            ints[0] -= 1
        self.address = "%02X:%02X:%02X:%02X:%02X:%02X"%tuple(ints)
        
        self._PDU = formatFactory(
            #@@@ Bit order of preamble, SFD, and FCS is not correct.
            # See 3.3 and 3.2.8
            [('preamble', 'ByteField', 56, chr(int('10101010', 2))*7),
             ('SFD', 'ByteField', 8, chr(int('10101011',2))),
             ('destAddr', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
             ('srcAddr',  'MACAddr', 48, self.address),
             ('typeOrLength', 'Int', 16, 0x0800),
             ('data', 'ByteField', None, None),
             ('FCS', 'Int', 32, None)], self)

        # Start accepting frames
        self._niu.XOFF = False
        
    def setAddress(self, address):
        """Set the MAC address."""
        self.address = address

    def addGroupAddress(self, mcAddress):
        """Add the provided multicast address to the address filter.

        Frames with this multicast address as destination are accepted and
        passed to the upper layer.

        Arguments:
          mcAddress:String -- Multicast address of the form '31:23:FA:3A:21:9A'
        """
        if mcAddress not in self._addressFilter:
            self._addressFilter.append(mcAddress)

    def deleteGroupAddress(self, mcAddress):
        """Remove the provided multicast address from the address filter.

        Frames with this multicast address will be discarded.

        Arguments:
          mcAddress:String -- Multicast address of the form '31:23:FA:3A:21:9A'
        """
        if (mcAddress != "FF:FF:FF:FF:FF:FF"  
            and mcAddress in self._addressFilter):
            self._addressFilter.remove(mcAddress)
            
    def receive(self, bitstream):
        """Receive a bitstream from the PHY layer, test it and pass it upwards.

        According to the standard, Section 4.2.4, this function has to
        - eliminate collision fragments (smaller than the minimum size)
        - discard carrierExtension in 1000 Mb/s mode
        - disassemble frame
        - check if destination address has to be accepted
        - check FCS sequence
        - if everything OK, pass the fields to the data link layer (LLC).
        """

        self._latestReceiveActivity = TIME()
        
        # Discard collision fragments that are shorter than a minimum frame
        if len(bitstream) < self._MIN_FRAMESIZE + 8:
            return

        # Chop of carrier extension in 1000 Mb/s mode.
        # Carrier extension is modeled as '\x00' octets.
        # @@@ FIXME FCS could be confused with carrier extension
        if (len(bitstream) == self._GIGA_SLOTTIME/8 + 8
            and self._niu.phy.getDataRate() == 1000e6
            and self._niu.phy.getDuplexMode() == HALF_DUPLEX):
            bitstream = bitstream.rstrip('\x00')

        # Parse the bitstream into a PDU format
        frame = self._PDU()
        frame.fill(bitstream)

        # Check if the frame shall be accepted
        destAddr = frame.destAddr
        if destAddr != self.address and destAddr not in self._addressFilter:
            return

        # Check FCS. Exclude preamble, SFD and FCS field
        checksum = crc32(bitstream[8:-4]) & ((1L<<32)-1) # take lower 32 bit
        if checksum != frame.FCS:
            print "FCS error"
            self.frameCheckSequenceErrors += 1
            return

        ACTIVITY_INDICATION(self, "rx", "receive")
        # All is correct. Deliver the frame content to the data link layer
        self.framesReceivedOK += 1
        self.octetsReceivedOK += len(frame.data)
        self._niu.dl.receive(destAddr, frame.srcAddr, frame.typeOrLength,
                              frame.data)
        
    def send(self, bitstream, destMACAddr, srcMACAddr, typeOrLength):
        """Construct a MAC frame for transmission and invoke media access.

        This method assembles a MAC frame from the provided data as described
        in the standard, Section 4.2.3.1. It then calls the medium access
        method that tries to acquire the medium and transmit the frame.

        This operation is not buffered and can only have a single frame
        in transmission. If it is called while the preceding frame has not yet
        complete transmission, an exception is raised.

        As soon as the medium access method has finished the transmission
        of the frame or if an error occured, it calls dl.sendStatus,
        to inform the upper layer.

        Arguments:
          bitstream:Bitstream -- Data to transmit.
          destMACAddr:String -- destination MAC address
          srcMACAddr:String -- source MAC address
          typeOrLength:Integer -- Encapsulated protocol type or data length
        Return value: None.
        """
        assert (self._niu.XOFF == False and not self._sendBuffer)
        self._niu.XOFF = True # Do not accept new frames while transmitting

        # Construct a PDU
        frame = self._PDU()
        frame.destAddr = destMACAddr
        frame.srcAddr = srcMACAddr
        frame.typeOrLength = typeOrLength
        # Add pad
        if len(bitstream) < self._MIN_FRAMESIZE - 18:
            bitstream += '\x00' * (self._MIN_FRAMESIZE - 18 - len(bitstream))
        frame.data = bitstream
        checksum = crc32(frame.serialize()[8:-4]) & ((1L<<32)-1)
        frame.FCS = checksum

        self._sendBuffer = frame
        self._transmissionAttemps = 0
        self._mediumAccess()

    def _mediumAccess(self):
        """Acquire the transmit medium, transmit the frame and inform dl.

        This function tries to transmit a current frame according to the
        CSMA/CD algorithm, as described in the standard, Section 4.2.3.2.
        The following elements of the standard are implemented:
          - Half duplex transmission: CSMA/CD
          - Full duplex transmission
          - Carrier sense (in half duplex)
          - Interframe spacing (in half and full duplex)
          - Collision detection and enforcement through jam (in half duplex)
          - Exponential backoff and retransmission (half duplex)
          - Carrier extension (in half duplex for data rate > 100 Mb/s
        The following elements are not implemented:
          - Frame bursting (used for data rates > 100 Mb/s).
        """

        assert(self._sendBuffer != None)

        if self._niu.phy.getDuplexMode() == FULL_DUPLEX:

            # Transmission without contention. Only respect interframe gap
            gaptime = self._INTERFRAME_GAP * self._niu.phy.bittime()
            currentgap = TIME() - self._latestTransmitActivity
            if  currentgap < gaptime:
                ACTIVITY_INDICATION(self, "tx", "gaptime", "grey", 3, 2)
                SCHEDULE(gaptime - currentgap, self._mediumAccess)
                return
            self._transmissionAttemps += 1
            ACTIVITY_INDICATION(self, "tx", "send FD", "green", 0, 0)
            self._niu.phy.transmitting(activate=True)
            self._niu.phy.send(self._sendBuffer.serialize())
            return

        else: # Transmission in half duplex mode

            # 1. Carrier sense
            if self._niu.phy.carrierSense():
                ACTIVITY_INDICATION(self, "tx", "carrierSense", "blue", 3, 2)
                self._waitingForIdleChannel = True
                # Wait until channel activities end. The MAC.channelIdle
                # method will call us then
                return
            self._waitingForIdleChannel = False
            
            # 2. Interframe gap
            gaptime = self._INTERFRAME_GAP * self._niu.phy.bittime()
            currentgap = TIME() - max(self._latestTransmitActivity,
                                      self._latestReceiveActivity)
            if  gaptime - currentgap > self._niu.phy.bittime()/100:
                ACTIVITY_INDICATION(self, "tx", "gaptime", "grey", 3, 2)
                gapjitter = gaptime * random()/100 # Avoid dicrete synchro.
                SCHEDULE(gaptime-currentgap+gapjitter, self._mediumAccess)
                return
            # 3. Here we go. Initiate the transmission. Wait for the
            #    transmissionCompleted or collisionDetect signal
            self._transmissionAttemps += 1
            ACTIVITY_INDICATION(self, "tx", "send HD", "green", 0, 0)
            self._niu.phy.transmitting(activate=True)
            self._niu.phy.send(self._sendBuffer.serialize())
            return

    def sendStatus(self,status,bitstream):
        """Terminate the transmission, inform dl, and clean up.

        This method is called from the phy layer, when a transmission
        previously initiated with PHY.send terminates.
        First check if we are sending a jam. In this case, the jam
        transmission has completed. Switch of the transmission and call the
        backoff method.
        If not jamming, terminate the transmission, update the statistics,
        clean up and inform the upper layer.

        A status==0 indicates success. Any other status indicates an error.
        """
        self._latestTransmitActivity = TIME()
        
        if self._jamming:
            ACTIVITY_INDICATION(self, "tx")
            self._niu.phy.transmitting(False)
            self._backoff()
            return

        ACTIVITY_INDICATION(self, "tx")
        self._niu.phy.transmitting(False) # Terminate the transmission
        if not status:
            self.framesTransmittedOK += 1
            self.octetsTransmittedOK += len(self._sendBuffer.data)
            if self._transmissionAttemps > 2:
                self.multipleCollisionFrames += 1
            if self._transmissionAttemps == 2:
                self.singleCollisionFrames += 1
        else:
            # Discard the frame and inform DL (LLC)
            self.octetsTransmittedError += len(self._sendBuffer.data)
            status = _UNKNOWN_TRANSMISSION_ERROR

        SCHEDULE(0.0, self._niu.dl.sendStatus, (status, self._sendBuffer))
        self._transmissionAttemps = 0
        self._sendBuffer = None
        self._niu.XOFF = False

    def collisionDetect(self):
        """In half duplex, send jam, compute backoff and schedule retransmit.

        This method is called from the PHY layer to indicate a collision.
        It implements the behavior described in the standard, Sec. 4.2.3.2.4
        (collision detection and enforcement).
        
        First check if we are already sending a jam. In this case do nothing.
        Otherwise, if we are in half duplex mode, enter jamming mode and
        send jam to enforce the collision.
        """

        if self._jamming or self._niu.phy.getDuplexMode() == FULL_DUPLEX:
            return

        ACTIVITY_INDICATION(self, "tx", "JAM", "red", 0,2)
        self._jamming = True
        self._niu.phy.send('\x00'*self._JAMSIZE)

    def channelIdle(self):
        """Test if _mediumAccess is waiting for idle channel and call it.

        This method is called by PHY as soon as the channel becomes idle.
        """
        if self._waitingForIdleChannel:
            self._mediumAccess()

    def _backoff(self):
        """Compute backoff and schedule retransmission.

        This method is called after the end of the jam transmission. In half
        duplex mode, it does the following:
        - compute a backoff
        - enter backoff mode
        - schedule the retransmission of the frame.
        If the maximum number of collisions is already reached, abandon the
        frame and signal an error to the upper layer.
        """

        ACTIVITY_INDICATION(self, "tx", "backoff", "blue", 1,2)
        self._jamming = False
        if self._transmissionAttemps >= 16:
            # Transmission failed. Update statistics, inform dl and clean up
            SCHEDULE(0.0, self._niu.dl.sendStatus,
                     (_EXCESSIVE_COLLISION_ERROR, self._sendBuffer))
            self.excessiveCollisions += 1
            print "Excessive collisions"
            self._transmissionAttemps = 0
            self._sendBuffer = None
            self._niu.XOFF = False
            return

        k = min(10, self._transmissionAttemps)
        r = int(random()*(1<<k))
        if self._niu.phy.getDataRate() == 1000e6:
            backoff = r * self._GIGA_SLOTTIME * self._niu.phy.bittime()
        else:
            backoff = r * self._SLOTTIME * self._niu.phy.bittime()
        SCHEDULE(backoff, self._mediumAccess)

class LLC(DLTop):
    """LLC sublayer that provides de-multiplexing to upper layers."""


    def __init__(self):
        self._upperLayers = {}
        self._transmissionBuffer = []
        
    def install(self, device, protocolName):
        if isinstance(device, Device):
            self._device = device
        else:
            raise TypeError("LLC layer entity must be installed on a device")
        if protocolName != "dl":
            raise NameError("LLC layer entity must be installed under "
                            "the name 'dl'")
        self._protocolName = "dl"
        self.fullName = device.fullName + ".dl"

    def setSrcAddress(self, srcMAC):
        """Set the MAC address of the entity."""
        self._device.mac.setAddress(srcMAC)

    def registerUpperLayer(self, upperProtocolEntity, protocolType=None):
        """Register an upper layer protocol to receive packet.

        If a received packet matches the protocolType, it is delivered to
        the upper layer protocol by calling its receive function.
        protocolType may be a numeric type or None to indicate that the
        protocol wants to receive all packets.

        Arguments:
          upperProtocolEntity:ProtocolEntity -- receiver of packets
          protocolType:Numeric or None: criterion which packets should be
                                        passed to the upper layer protocol.
        Return value: None.
        """
        up = self._upperLayers.get(protocolType, [])
        up.append(upperProtocolEntity)
        self._upperLayers[protocolType] = up 

    def send(self, bitstream, destMAC, srcMAC, protocolType):
        """Accept a bitstream from the NW layer and try to send it.

        If it cannot be sent, put it into a transmission buffer and wait
        until MAC becomes available for the next packet (call of sendStatus).
        """
        self._transmissionBuffer.append((bitstream,destMAC,
                                         srcMAC,protocolType))
        if not self._device.XOFF:
            self._trySending()

    def receive(self, destMAC, srcMAC, protocolType, bitstream):
        """Accept a pdu from the DLBottom. Analyze the protocol type and
        demultiplex it accordingly to the upper layer protocols.
        """
        if len(bitstream) == 46:
            # Remove pad
            bitstream = bitstream.rstrip('\x00')
        for upperLayer in self._upperLayers.get(protocolType, []):
            upperLayer.receive(bitstream)

    def sendStatus(self, status, pdu):
        """Called by DLBottom at the end of a transmission.

        The status indicates if the transmission was successful or if
        there was an error.
        """
        # Inform upper layer
        # @@@ This is not clean
        bitstream, destMAC, srcMAC, protocolType = self._outstandingFrame
        self._outstandingFrame = None
        for upperLayer in self._upperLayers.get(protocolType, []):
            upperLayer.sendStatus(status, bitstream)
        self._trySending()

    def _trySending(self):
        """If the MAC allows sending a new packet, send one."""
        if not self._device.XOFF and self._transmissionBuffer:
            self._outstandingFrame = self._transmissionBuffer.pop(0)
            bitstream, destMAC, srcMAC, protocolType = self._outstandingFrame
            self._device.mac.send(bitstream, destMAC, srcMAC, protocolType)

        
