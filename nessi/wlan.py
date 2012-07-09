# Nessi Network Simulator
#
# Authors:  Jerome Vernez; IICT HEIG-VD
# Creation: August 2005
#
# Copyright (c) 2003-2007 Juergen Ehrensberger, Jerome Vernez
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
Physical, MAC and LLC layer protocol entities for the Wireless LAN IEEE 802.11e
protocol.

The module exports the following classes:
    - PHY: Physical layer entity for the 802.11e protocol.
    - MAC: Medium Access Control sublayer for the 802.11e protocol.
    - LLC: Link Layer Control sublayer according to 802.2, type 1.
    - PseudoNW: Simule a simple Network layer with a MTU = 1500 octets.
"""

__all__ = ["PHY", "MAC", "LLC", "PseudoNW"]

from random import random, randint
from zlib import crc32
from netbase import ProtocolEntity, NIU, Device
from netbase import PhyLayer, DLBottom, DLTop
from devices import NIC, AP, QAP, WNIC, QWNIC

from wlanDef import *

from simulator import SCHEDULE, SCHEDULEABS, CANCEL, TIME, ACTIVITY_INDICATION, TRACE



class PHY(PhyLayer):
    """
    Physical layer entity for the Wireless LAN IEEE 802.11e protocol.

    The task of the physical layer is to accept bits from the MAC
    sublayer and to transmit them over the attached medium as well as
    to receive bits from the medium and pass them to the MAC.
    
    It provides information to the MAC sublayer if the medium is idle
    or occupied (=carrier sense). Collision detect is not possible on this PHY.
    This PHY layer will be able simulate signal attenuation or bit errors.
    
    It provides time compute to the MAC sublayer too (IFS).

    The choice of the Bitrate will affect the type of PHY Layer:
        - FHSS: 1, 2 Mbps (802.11)
        - DSSS: 5.5, 11 Mbps (802.11b)
        - OFDM: 6, 9, 12, 18, 24, 36, 48, 54 Mbps (802.11g)
    
    
    The PHY MIB is not used because the variables who composes it concerne only the
    material. For a simulation it's not necessary.
    
    The Header of the PHY frame are virtual. The value of bits are not present.
    The constants PreambleLength and PLCPHeaderLength (in class PhyModulation)
    are used to determine the time that take the transmission of the PHY Header.
    
    The CCA are not made every symbol. Only one is made at the end of send and
    receive data to informed MAC of the channel idle. The others they are
    commanded by the MAC.


    Interface provided to the medium:
        - newChannelActivity :  Called by the medium when another NIU starts
                                transmitting.
        - receive :             Receive the data of a transmission from the medium.


    Interface provided to the MAC layer:
        - carrierSense :  True, if the medium is occupied, False otherwise.
        - send :          Called by the MAC layer to transmit a PPDU.
        - getSlotTime:    Return the Slot Time of PHY layer to compute times variables in MAC sublayer level.
        - getCW:          Provide the CWmin and CWmax.
        - computeIFS:     Compute the four IFS for the MAC sublayer.
        - getTimeLastReceiveActivity: Return the time when the last receive activity has begun.
        - getTransmissionTime: Return the time than take the transmission of x bits


    Configuration interface:
        - install :       Install the protocol entity as 'phy' on a NIU.
        - setDataRate :   Set the data rate of the physical interface.
        - getDataRate :   Return the data rate of the physical interface.
    """


    def __init__(self):
    
        self._mod = PhyModulation()
        """PHY constants 802.11 (default: FHSS)"""

        # Private fields - General
        self._dataRate = 1e6
        """Data rate for transmission. In bits/s. Type: float."""
        self._receiveActivities = 0
        """Number of receive transmission to the current entity. Type:Integer."""
        self._receiveStartTime = None
        """Start time of receive activity on the channel. Type:Float."""
        self._collisionDetect = False
        """Flag whether the was a collision in the channel. Type:Boolean."""
        self._transmitStartTime = None
        """Start time of the outgoing transmission. Type:Float."""
        self._transmittedData = None
        """Bitstream that has to be send onto the medium. Type:Bitstream."""
        
        # Statistics variable
        self.nbCollision = 0
        """Statistitic value to know the number of collision (transmission and reception)"""


    def setDataRate(self, dataRate):
        """
        Set the data rate of the physical interface:
            - 802.11  : 2, 1 Mbps
            - 802.11b : 11, 5.5, Mbps
            - 802.11g : 54, 48, 36, 24, 18, 12, 9, 6 Mbps
            
        Set the 802.11 PHY constants in function of data rate.   
            
        @type dataRate:     Integer
        @param dataRate:    Data rate of the physical interface.
        
        @rtype:             None
        @return:            None
        """
        if dataRate in (1e6, 2e6, 5.5e6, 6e6, 9e6, 11e6, 12e6, 18e6, 24e6, 36e6, 48e6, 54e6):
            self._dataRate = dataRate
        else:
            raise ValueError("Invalid data rate on Wlan 802.11 NIU "
                             + self._niu._node.hostname + "."
                             + self._niu.devicename
                             + ".phy: " + `dataRate`)

        #Update the PHY constants
        if dataRate in (1e6, 2e6):
            #FHSS constants
            self._mod.FHSS()
        
        elif dataRate in (5.5e6, 11e6):
            #DSSS constants
            self._mod.DSSS()
        
        else:
            #OFDM shorts constants
            self._mod.OFDM()
        


    def getDataRate(self):
        """
        Get the PHY datarate.
        
        @rtype:     Integer
        @return:    The data rate of the physical interface.
        """
        
        return self._dataRate
        
        
        
    def getTimeLastReceiveActivity(self):
        """
        Get the last time when a reception activity occurred.
        
        @rtype:     Float
        @return:    The time when the last receive activity has begun.
        """
        
        return self._receiveStartTime
        
        
        
    def getTransmissionTime(self, dataLength):
        """
        Return the time used for a x bits transmission.
        
        @type dataLength:       Integer
        @param dataLength:      Length of data to tranmsit in bit.
        
        @rtype:                 Float
        @return:                The time than take the transmission with the current bitrate.
        """
        
        return self._mod.preambleLength + self._mod.plcpHeaderLength + dataLength*8 / self._dataRate

        
        
    def getSlotTime(self):
        """
        @rtype:     Float
        @return:    The slot time of the current modulation to compute the Backoff time in MAC sublayer
        """

        return self._mod.slotTime
        
        
        
    def getCW(self, minOrMax):
        """
        Provide the CWmin or CWmax.
        
        @type minOrMax:     String
        @param minOrMax:    To select the CWmin or CWmax by 'min' or 'max'
        
        @rtype:             Integer
        @return:            The CWmin or CWmax.
        """

        if (minOrMax == 'min'):
            return self._mod.cwMin
        elif (minOrMax == 'max'):
            return self._mod.cwMax
        else:
            raise ValueError("Invalid paramater for the PHY Method: cw(minOrMax)")
        
        
    def newChannelActivity(self):
        """
        Register a new channel activity and collisions transmissions.

        Called by the medium when another NIU starts transmitting. The
        method determines if the new transmission causes a collision
        (collision with transmissions of other NIUs). Collisions
        are remembered to later invalidate the received data before passing
        it to the MAC.
        
        @rtype:     None
        @return:    None
        """
        
        self._receiveActivities += 1
        self._receiveStartTime = TIME()
        
        if self._receiveActivities == 1 and not self._transmittedData:
            self._collisionDetect = False
            
        else:
            self._collisionDetect = True

   
        
    def receive(self, bitstream):
        """
        Receive the data of a transmission from the medium.

        Called by the medium when the transmission of an NIU ends.
        If this was the only incoming transmission, then the received data is
        delivered to the MAC.
        
        If it's a overlapping incoming transmission, then corrupted data is 
        delivered to the MAC. The length of the data is determined by the total
        time of uninterrupted reception:
        
        ((end of last transmission) - (start of first tx)) * data rate
        
        
        @type bitstream:    Bitstream
        @param bitstream:   Block of data to transmit onto the medium.
        
        @rtype:             None
        @return:            None
        """
        
        self._receiveActivities -= 1
        
        if self._receiveActivities > 0:
            #Collision period
            #It's not possible to retrieve the good receiveStartTime.
            #Wait the last receive to count the collision
            return
        
        #If there was collision detection, update statistics and
        #the data collisioned is not retourned to the MAC sublayer.
        if self._collisionDetect:
            self.nbCollision += 1
            self._collisionDetect = False
            return

                             
        #Reception is finished. Pass received data to the MAC.                              
        bytelen=int(((TIME()-self._receiveStartTime-self._mod.preambleLength-self._mod.plcpHeaderLength)*self._dataRate + 0.05)/ 8)
        
        if len(bitstream) != bytelen:
            raise ValueError("Speed mismatch on radio channel "
                             + self._niu._node.hostname + "."
                             + self._niu.devicename
                             + ".phy: received data with invalid length")
                             
        self._niu.mac.receive(bitstream)

        #If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.mac.channelIdle()



    def carrierSense(self):
        """
        Make a CCA to know the channel occupation.
        
        This method guarantee an eventual collision with a transmission 
        demand by the MAC sublayer in the same time (< 1 TU).
        
        @rtype:     Boolean
        @return:    Channel occupation (True if it's occupied, False otherwise).
        """
        
        #The MAC sublayer must have still the right to make a transmission during
        #one SlotTime (Backoff unit). It's guarantee an eventual transmission collision.
        if self._receiveStartTime:
            if TIME()-self._receiveStartTime < self._mod.slotTime:
                #Autorize MAC sublayer to send. Last receive activities is too recent.
                #It's permit to guarantee an eventual collision.
                return False

        return ((self._receiveActivities > 0) or self._transmittedData)




    def send(self, bitstream):
        """
        Called by the MAC layer to transmit a block of data.
        Simule the transmission on the medium by waiting the 
        transmission delay.
        
        The total transmission of PPDU take the following time:
        
            - PHY Header: PreambleLength + PLCPHeaderLength
            - MSDU: SizeMSDU / dataRate

        @type bitstream:    Bitstream
        @param bitstream:   Block of data to transmit onto the medium.
        
        @rtype:             None
        @return:            None
        """
        
        if self._transmittedData == None:
            self._transmittedData = bitstream
            self._transmitStartTime = TIME()
            
            self._niu.medium.startTransmission(self._niu)
            
            #Control the presence of an eventual collision
            if self._receiveActivities > 0 :
                self._collisionDetect = True
            else:
                self._collisionDetect = False            

            transmissionDelay = self.getTransmissionTime(len(bitstream))
            SCHEDULE(transmissionDelay, self._completeTransmission)

        else:
            raise ValueError("It is not possible to send new data during a current transmission.")

           


    def _completeTransmission(self):
        """
        Terminate the transmission and inform the MAC that PHY has finished
        transmitting the data.
        
        @rtype:     None
        @return:    None
        """

        # Terminate the transmission (Send the data to the medium and clean up)
        bytelen=int(((TIME()-self._transmitStartTime-self._mod.preambleLength-self._mod.plcpHeaderLength)*self._dataRate + 0.05)/8)
        bitstream = self._transmittedData[0:bytelen]
        
        self._niu.medium.completeTransmission(self._niu, bitstream)
        self._transmittedData = None
        self._transmitStartTime = None
        
        #Inform MAC than transmission is finished
        #It's not possible to know if errror is occured
        #The parameters in not used
        self._niu.mac.sendStatus(0, None)
        
        #If channel is now idle, inform the MAC
        if not self.carrierSense():
            self._niu.mac.channelIdle()
            


    def computeIFS(self, AIFSN=2):
        """
        Compute the four IFS for the MAC sublayer:
            - Short Inter Frame Space (SIFS)
            - PCF Inter Frame Space (PIFS)
            - AIFS Arbitrary Inter Frame Squence Number
              (=DCF Inter Frame Space (DIFS) if AIFSN is not defined)
            - Extended Inter Frame Space (EIFS)
            
        @type AIFSN:    Integer
        @param AIFSN:   Arbitrary Inter Frame Sequence Number
            
        @rtype:     Tuple of Integer
        @return:    sifs, pifs, aifs (or difs), eifs in a tuple
        """
        
        sifs = self._mod.sifsTime
        """Short Interframe Space. Definition: 9.2.10"""
        pifs = self._mod.sifsTime + self._mod.slotTime
        """PCF Interframe Space. Definition: 9.2.10"""
        difs = self._mod.sifsTime + 2*self._mod.slotTime
        """DCF Interframe Space. Definition: 9.2.10"""
        aifs = self._mod.sifsTime + AIFSN*self._mod.slotTime
        """DCF Interframe Space. Definition: 9.2.10"""
        eifs = self._mod.sifsTime + 112e-6 + self._mod.preambleLength + self._mod.plcpHeaderLength + difs
        """Extended Interframe Space (396us for FHSS / 364us for DSSS). 
        112us = 8*ACKSIZE(14 octets)/1Mbps (lowest rate). Definition: 9.2.10"""
    
        return (sifs, pifs, aifs, eifs)
    

        
class MAC(DLBottom):
    """
    Channel Access Control sublayer for the Wireless LAN IEEE 802.11e protocol.
    
    Implementation of 802.11:
        - DCF Mode in BSS
        - MAC Data service
        - Management Information Base (MIB)

    Not Implemented:
        - WEP
        - Power management
        - MAC Fragmentation
        - RTS/CTS
    
    Implementation of 802.11e:
        - QoS frame format
        - 4 Backoff entities
        - Multiple frame transmission support
        - HCF controlled channel access rules
        - HCF controlled channel access schedule generation and management
        - HCF frame exchange sequences (partially)
        
    Not implemented:
        - Decode of no-ack policy in QoS data frames
        - Block acknowledgements
        - Direct Link Set-up
        - Contention-based admission control
        - TSPEC and associated frame formats
        - TS Management

    
    This MAC implementation manage 3 modes of channel access:
        - DCF (Distributed Coordination Function)
        - EDCA (Enhanced Distributed Channel Access)
        - HCCA (HCF Controlled Channel Access)
        
        
    DCF is the mainly channel access for the 802.11 standard. EDCA and HCCA correspond of two access method
    of HCF (802.11e). HCF enhancement the basic 802.11 with a best quality of service (QoS). It possible 
    to commute between this three modes with the simulation script.
    
    This MAC implementation manage 4 types of device:
        - WNIC
        - QWNIC
        - AP
        - QAP
        
    But a QoS device can't communicate with a non-Qos device. The non-QoS devices
    is used only for the DCF mode.
        
  
    The MAC layer works by state. A state meaning a waiting in a certain operating 
    mode. For each new action to realize (methods), it will be possible to control 
    if the action is feasible according to the current state. The first thing to be 
    made in each method of send and reception is to control the current state. 
    There are 7 possible states of the MAC layer :

        - IDLE :	    The MAC is idle.
        - SEND_DATA :	Period of sending a data frame.
        - SEND_ACK :	Period of sending a ack frame.
        - SEND_BEACON :	Period of sending of a beacon frame.
        - SEND_CFPOLL : Period of sending of a QoS CF-POLL frame.
        - SEND_CFEND :  Period of sending of a QoS CF-END frame.
        - WAIT_ACK :	Period of waits which follows the sending of a frame of data by waiting a ACK frame.

    
    The main functionality of this MAC implementation is the access to the channel. This one is described by 
    the method channelAccess(). This method obliges all transmissions of frames to pass by 5 stages:
    
        1. Carrier Sense (PHY & MAC)
        2. Interframe space
        3. Backoff procedure (Optionnal)
        4. TBTT Procedure Control
        5. Phy sending
   
    
    When frames forward by the AP, but that they are not intended to him,
    the MAC AP transmit these frames to the upper layer (In a BSS for STA to
    STA, the ToDS Bit is obligatory positive).
    
    The CCA (Carrier Sense) are not made every symbol. It is made at the
    important moment only in the _channelAccess() method:
        - When we make the transmission (before IFS)
        - After IFS (just before the transmission or before Backoff)
        - After Backoff (just before the transmission)
    
    
    he MAC implementation manage a systeme of statistique of all actions. The statistics
    is used by the sink to show graphical results.
    
    
    Interface provided to the PHY layer:
        - sendStatus:       Status of the last transmission given by the PHY layer.
        - receive:          Receive the data of a transmission from the PHY layer.
        - channelIdle:      The PHY layer advertise the MAC sublayer as soon as the 
                            channel becomes idle after a activity.

    Interface provided to the LLC layer:
        - send:             Called by the LLC layer to transmit a MSDU.


    Configuration interface:
        - install:          Install the protocol entity as 'mac' on a NIU.
        - config:           Configure the main MAC variables.
        - configEDCATable:  Configure the EDCA Table.
        - getMacAddr:       Give the MAC address of the current entity.
        
        
    Internal method:

    SEND METHODS:
    
        - _selectNextMSDU:  Choose the next MSDU to send.
        - _selectSTAPoll:   Select the QSTA to poll.
        - _sendData:        Construct the Data frame and access to the channel to send it.
        - _sendQosCfPoll:   Construct a QoS CF-Poll frame and access to the channel to send it.
        - _sendCfEnd:       Construct a CF-End frame to end the Contention Free Period. 
                            Access to the channel to send it.
        - _sendBeacon:      Manage the regular sending of Beacons when the Beacon Management was enabled.
        - _sendAck:         Contruct an ACK frame to send it to the entity who has sent the last data frame.
        - _retransmission:  Do a retransmission of a data frame (because of Ack timeout).
        
        
    RECEIVE METHODS:

        - _receiveData:     Reception of a data frame.
        - _receiveAck:      Reception of a Ack frame.
        - _receiveQosCfPoll:Reception of a QoS CF-Poll frame.
        - _receiveCfEnd:    Reception of an CF-End frame by a QSTA.
        - _receiveBeacon:   Reception of a Beacon frame.
        
        
    CONTROL METHODS:
        
        - _checkData:       Validation of a data frame.
        - _duplicateData:   Test if the last data frame received is a duplicate.
        - _checkAck:        Validation of a Ack frame.
        - _checkCfEnd:      Validation of a CF-End frame.
        - _checkBeacon:     Validation of a Beacon frame.
        - _controlFCS:      Test with the Frame Check Sequence.
        
        
    CSMA-CA METHODS:   
        
        - _backoff:         Backoff management (decide if Backoff must be applied).
        - _computeBackoff:  Compute the random Backing Off in number of Slot Time.
        - _endBackoff:      Cloture a Backoff procedure.
        
        
        
    BEACON METHODS:
    
        - _startBeacon:     Begin a new Beacon Management.
        - _stopBeacon:      Stop the Beacon Management.
    
        
    OTHERS METHODS:
    
        - _channelAccess:   Try to have the access to the channel (5 states).
        - _IFS:             Interframe Space management.
        - _saveMacState:    Save the state of the MAC sublayer.
        - _restoreMacState: Restore a previous saved state of MAC sublayer.
        - _txContinue:      Test if another MSDU is present in transmissions queue
                            to continue to transmit.
        - _newTBTT:         Set a new TBTT when the Beacon Interval has changed or 
                            for the first TBTT.
        - _setTBTT:         Set the TBTT every Beacon Interval by event.
        - _setNAV:          The period of Network Allocation Vector is started or updated.
        - _endNAV:          Cloture a Network Allocation Vector.
        - _terminMac:       Initialisation of the privates variables for the next transmission.
        - _discardMsdu:     Discard MSDU id of the transmissions queues indicated.
        
    """

    # MAC constants.
    _MAX_MSDUSIZE = 2034 #octets
    """Maximum permit size of a MSDU."""
    _ACKSIZE = 14 #octets
    """Size of a MAC acknowlegdgement."""
    _DATAHEADER = 36
    """Default value for the size of QoS data frame header (with footer)."""
    _TIME_UNIT = 1e-3 #seconds (Default in standard: 1024us)
    """TU is the official time unit for use in the MAC frame"""
    _MIN_UNIT = 1e-6 #seconds
    """1e-6 is the min time unit use in 802.11. Use often to round up a time. """
    
        
    
    def __init__(self):
        """
        Initialize variables for internal use.
        """
        
        #Enumeration "constants"
        self._frameType = MacFrameType()
        self._frameSubType = MacFrameSubType()
        self._state = MacState()
        self._status = MacStatus()

        
        #Private fields - General
        self._mib = MacMIB()
        """MAC Management Information Base."""
        self._bib = BSSInfoBase()
        """MAC BSS Information Base. Initialize the BSS and AP address (not compliant with standard)."""
        self._macState = self._state.IDLE
        """Actual state of the MAC layer."""
        self._sendBuffer = None
        """Contains the current frame to send."""
        self._macSave = {"lastMacState": self._state.IDLE,
                             "lastSendBuffer": None}
        """Save of main variable of the last state of the MAC sublayer. Dictionnary."""
        self._fragmentNb = 0
        """Actual Fragment Number (0 to 15)."""
        self._sequenceNb = randint(0, 4095)
        """Actual Sequence Number (0 to 4095)."""
        self._msduId = 0
        """Identity number for the MSDUs present in transmission queue (modulo 255)."""
        self._txInProgress = False
        """Indicate if a transmission is in progress."""
        self._mode = "HCCA"
        """Indicate the access mode for the 802.11 (DCF, EDCA or HCCA)"""
        
        
        #Private fields - Time relation
        self._latestTransmitActivity = 0.0
        """End time of the latest transmission. Used to compute interframe gap."""
        self._latestReceiveActivity = 0.0
        """End time of the latest reception. Used to compute interframe gap."""
        self._latestStartTransmitActivity = 0.0
        """Start time of the latest transmission. Used to compute interframe gap."""
        self._startProcedureTime = 0.0
        """Start time of the tranmission procedure (before the IFS and Backoff)."""
        self._IFSEventId = None
        """Event id scheduled when the IFS is finished."""
        
        
        #Private fields - CSMA-CA & Backoff procedure
        self._applyBackoff = False
        """Indicate if a Backoff must be applicate for the next transmission."""
        self._backoffEventId = None
        """Event id scheduled when the backoff is finished. It's permit to test if we are in phase of a Backing off too."""
        
        
        #Private fields - Retransmission procedure
        self._retryEventId = None
        """Event id scheduled when a retransmission could be to realize."""
        self._lastFrameError = False
        """Indicate if the last receive frame was erroneous. During the period that this variable is true, EIFS replace DIFS."""
        self._infoFramesCache = []
        """Cache Information concerned the last frames received. Definition: 9.2.9"""
        self._ackTimeout = 10 #[TU]
        """Unit Time waited by the source STA before make the retransmission of data frame.
           The standard 802.11 don't specify this value."""
           
           
        #Private fields - Beacon management
        self._beacon = False
        """Indicate if the Beacon management is active."""
        self._beaconEventId = None
        """Event id scheduled when a Beacon frame must be send."""       
        self._targetBeaconTxTime = 0
        """Target Beacon Transmission Time (TBTT). When the next Beacon must be transmitted."""
       
       
        #Private fields - TXOP & NAV management
        self._txop = False
        """Indicate if the TXOP period is active."""
        self._remainTXOP = 0.0
        """Remaining of TXOP time in time unit."""
        self._navEventId = None
        """Event id scheduled when the NAV period is terminated. Indicate if a NAV period is active."""
       
        
        #Private fields - Backoff Entity
        self._backoffEntityTransmit = None
        """The actual Backoff Entity in transmission (DCF, AC_BK, AC_VI, AC_BE or AC_VO)."""
        
       
        #Private fields - Superframe
        self._poll = False
        """Indicate if poll is autorised or not by the QAP"""
        self._cap = False
        """Indicate if a CAP period is active."""
        self._cfp = False
        """Indicate the period of Contention Free."""
        self._endCfpMax = 0
        """The max end of the CFP. A CFP has a maximum of a half Beacon Interval."""
        
        
        #Hybrid Coordinator
        self._hc = HC()
        
        
        #Statistics
        self.stat = MacStat()
        """MAC Statistics (use by application layer)."""
       

    
    
    def install(self, niu, protocolName):
        """
        This method is called by the one of following NIU (device) to inform
        the protocol that is has been installed :
            - WNIC (Wireless Network Interface Card)
            - QWNIC (QoS Wireless Network Interface Card)
            - AP (Access Point)
            - QAP (QoS Access Point)


        (Q)STA are automatically associated with the BSS. (Using the same BSS Id than the (Q)AP)
        
        The method initialize the MAC protocol:
            - Register the NIU for later access
            - Initialize the MAC MIB and choose a random MAC address
            - Choose a random BSS address for AP or QAP
            - Create the structure class for the use of the types of MAC frame  
                - Frame Control field (7.1.3.1)
                - Sequence Address field (7.1.3.4)
                - QoS Control field (7.1.3.5)
                - Data frame (with and without QoS) (7.2.2)
                - ACK frame (7.2.1.3)
                - Management frame (Beacon) (7.2.3)
                
                
        @type niu:              NIU
        @param niu:             NIU on which self is installed. Must be WNIC, QWNIC, AP or QAP.

        @type protocolName:    String
        @param protocolName:   Name of protocol. Must be 'mac'.

        @rtype:                 None
        @return:                None
        """

        if isinstance(niu, NIU):
            if (niu.__class__ == NIC):
                raise TypeError("802.11 MAC sublayer could not be installed on a NIC")
            self._niu = niu
        else:
            raise TypeError("802.11 MAC sublayer must be installed on a NIU (AP, QAP, WNIC or QWNIC)")
            
        if protocolName != "mac":
            raise NameError("802.11 MAC sublayer must be installed under the "
                            "name 'mac'")
        self._protocolName = "mac"
        self.fullName = niu.fullName + ".mac"
        
        
        #Reset the MAC Management Information Base (MAC Address attribution)
        #For (Q)STAs the MAC address is a random value
        self._mib.reset()
        
        
        #Set the (Q)AP MAC address (48 bits)
        #For (Q)APs the MAC address is a fixed value (in wlanDef.py)
        if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
            self._mib.address = self._bib.apAddr
       
        
        #Private fields - EDCA & DCF Backoff Entities
        #Obtain PHY informations
        cwMin = self._niu.phy.getCW('min')
        cwMax = self._niu.phy.getCW('max')
        dataRate = self._niu.phy.getDataRate
        if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
            #Private fields - EDCA
            self.AC_BK = BackoffEntity("AC_BK", cwMin, cwMax, dataRate)
            self.AC_BE = BackoffEntity("AC_BE", cwMin, cwMax, dataRate)
            self.AC_VI = BackoffEntity("AC_VI", cwMin, cwMax, dataRate)
            self.AC_VO = BackoffEntity("AC_VO", cwMin, cwMax, dataRate)
            self._edcaParamUpdateCTR = 0
            """Count the number of time than EDCA Parameter are updated"""
        else:
            #Private fields - DCF
            self.DCF = BackoffEntity("DCF", cwMin, cwMax, dataRate)
            
        
        #Structure of MAC frame fields
        self.format = MacFrameFormat()
        
        
        #Structures QoS / non-QoS
        if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
            #With QoS Control field
            self.MPDUFormat = self.format.MPDUQos
            self.BeaconDataFormat = self.format.BeaconDataQos
        else:
            #Without QoS Control field
            self.MPDUformat = self.format.MPDU
            self.BeaconDataFormat = self.format.BeaconData
            
        
        
        #Start Beacon Management for AP
        if self._niu.__class__ == AP or self._niu.__class__ == QAP:
            self._startBeacon()
        
        
        #Init HC
        if self._niu.__class__ == QAP:
            self._hc.queueSize[self._bib.apAddr] = [0, 0, 0, 0]
        
        
        
    def config(self, mode="HCCA", dataRate=1e6, bi=5.0, dtim=200e-3, ackTimeout=10e-3, assTimeout=600e-3, fragThre=2346, rts_ctsThre=2347):
        """
        Configure the main MAC variables.
        
            @type mode:         String
            @param mode:        Access mode using: DCF, EDCA, HCCA or EDCA+. Default=HCCA.
        
            @type dataRate:     Integer
            @param dataRate:    0=best/1e6/2e6/5.5e6/11e6/6e6/9e6/12e6/18e6/24e6/36e6/48e6/54e6. Default=1e6.
            
            @type bi:           Float
            @param bi:          Beacon interval (1ms - 65.535s). Default=5
            
            @type dtim:         Float
            @param dtim:        Delivery Traffic Indication Message (1ms - 255 ms). Default=0.2.
            
            @type ackTimeout:   Float
            @param ackTimeout:  ACK Timeout (1 - 100 ms). Default=10e-3. Correspond to the retransmission Timeout.
            
            @type assTimeout:   Float
            @param assTimeout:  Association Timeout (60 - 6000 ms). Default=600e-3.
            
            @type fragThre:     Integer
            @param fragThre:    Fragmentation threshold (256 - 2346). Default=2346.

            @type rts_ctsThre:  Integer
            @param rts_ctsThre: RTS/CTS threshold (0 - 2347). Default=2347.
            
            @rtype:             None
            @return:            None
        """
        
        #Mode
        if mode == "DCF" or mode == "EDCA" or mode == "HCCA" or mode == "EDCA+":
            self._mode = mode
        else:
            print("Error Config: Mode must be ""DCF"", ""EDCA or ""HCCA"" or ""EDCA+"". We take the Default value: HCCA")
            self._mode = "HCCA"
        
        #DataRate
        if (dataRate == 0):
            self._niu.phy.setDataRate(54e6)
        else:
            self._niu.phy.setDataRate(dataRate)
            
        if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
            if (dataRate != 1):
                #Obtain PHY info
                cwMin = self._niu.phy.getCW('min')
                cwMax = self._niu.phy.getCW('max')
                dataRate = self._niu.phy.getDataRate
                #Adapt the new DataRate with the 4 EDCAs Tables by default PHY Values
                self.AC_BE.resetEDCATable("AC_BK", cwMin, cwMax, dataRate)
                self.AC_BK.resetEDCATable("AC_BE", cwMin, cwMax, dataRate)
                self.AC_VI.resetEDCATable("AC_VI", cwMin, cwMax, dataRate)
                self.AC_VO.resetEDCATable("AC_VO", cwMin, cwMax, dataRate)
            
        #Beacon interval
        if ((bi<0.001) or (bi>65.535)):
            print("Error Config: Beacon Interval must be between 1us and 65.535 s. We take the Default value: 5")
            bi = 5.0
        self._bib.beaconInterval = int(bi/self._TIME_UNIT) # in [TU]
        #BI must be a multiple of the TU
        newbi = self._bib.beaconInterval*self._TIME_UNIT
        if newbi != bi:
            print("Beacon Interval is arround to the nearest TU. New value of BI = %f" %newbi)
            
        
        #Dtim interval
        if ((dtim<1e-3) or (dtim>255e-3)):
            print("Error Config: Dtim must be between 1ms and 255 ms. We take the Default value: 200 ms")
            dtim = 0.2
        self._bib.dtim = int(dtim/self._TIME_UNIT) # in [TU]
        #DTIM must be a multiple of the TU
        newdtim = self._bib.dtim*self._TIME_UNIT
        if newbi != bi:
            print("Dtim is arround to the nearest TU. New value of Dtim = %f" %newdtim)
        
        #Ack Timeout
        if ((ackTimeout<1e-3) or (ackTimeout>100e-3)):
            print("Error Config: Ack Timeout must be between 1ms and 100 ms. We take the Default value: 10 ms")
            ackTimeout = 10e-3
        self._ackTimeout = int(ackTimeout/self._TIME_UNIT) # in [TU]
        
        #Association Timout@@@
        
        #Fragmentation threshold
        if ((fragThre<256) or (fragThre>2346)):
            print("Error Config: Fragmentation threshold must be between 256 and 2346 ms. We take the Default value: 2346")
            fragThre = 2346
        self._mib.fragmentationThreshold = fragThre
        
        #RTS/CTS threshold
        if ((rts_ctsThre<0) or (rts_ctsThre>2347)):
            print("Error Config: RTS/CTS threshold must be between 0 and 2347 ms. We take the Default value: 2347")
            rts_ctsThre = 2347
        self._mib.rtsThreshold = rts_ctsThre
    
    
    
    
    
    def configEDCATable(index, ecwMin=5, ecwMax=10, aifsn=7, txopLimit=0, msduLifeTime=500):
        """
        Configure the EDCA Table. This Table must be configure after the method config
        because this method config initialize the EDCA tables with the default PHY values.


        @type index:        Integer
        @param index:       index = 1: AC_BK, index = 2: AC_BE, index = 3: AC_VI, index = 4: AC_VO
            
        @type ecwMin:       Integer
        @param ecwMin:      Exponential of 2 to calculate contention window min in TU (0 - 8). Default=5.
            
        @type ecwMax:       Integer
        @param ecwMax:      Exponential of 2 to calculate contention window max in TU (0 - 16). Default=10.
            
        @type aifsn:        Integer
        @param aifsn:       Arbitrary Interframe Space Number (2 - 15). Default=7.
            
        @type txopLimit:    Integer
        @param txopLimit:   Association Timeout (0 - 65535). Default=0.
            
        @type msduLifeTime: Integer
        @param msduLifeTime:Fragmentation threshold (0 - 500). Default=500.
            
        @rtype:             None
        @return:            None
        """
        
        #ECWmin
        if ((cwMin<0) or (cwMin>255)):
            print("Error Config: ECWmin must be between 0 and 8 TU. We take the Default value: 5")
            cwMin=5
        
        #ECWmax
        if ((cwMax<0) or (cwMin>65535)):
            print("Error Config: ECWmax must be between 0 and 16 TU. We take the Default value: 10")
            cwMax=10
        
        #AIFSN
        if ((aifsn<2) or (aifsn>15)):
            print("Error Config: AIFSN must be between 2 and 15. We take the Default value: 7")
            aifsn=7
        
        #TXOPLimit
        if ((txopLimit<0) or (txopLimit>65535)):
            print("Error Config: TXOPLimit must be between 0 and 65535 ms. We take the Default value: 0")
            txopLimit=0
            
        #MSDULifeTime
        if ((msduLifeTime<0) or (msduLifeTime>500)):
            print("Error Config: MSDULifeTime must be between 0 and 500 TU. We take the Default value: 500")
            msduLifeTime=500
        
        #Count the number of time than the EDCA are updated
        self._edcaParamUpdateCTR += 1
    
        if index == 1: #AC_BK
            self.AC_BK.EDCATable.CWmin = 2**ecwMin-1
            self.AC_BK.EDCATable.CWmax = 2**ecwMax-1
            self.AC_BK.EDCATable.AIFSN = aifsn
            self.AC_BK.EDCATable.TXOPLimit = txopLimit
            self.AC_BK.EDCATable.MSDULifeTime = msduLifeTime
       
        elif index == 2: #AC_BE      
            self.AC_BE.EDCATable.CWmin = 2**ecwMin-1
            self.AC_BE.EDCATable.CWmax = 2**ecwMax-1
            self.AC_BE.EDCATable.AIFSN = aifsn
            self.AC_BE.EDCATable.TXOPLimit = txopLimit
            self.AC_BE.EDCATable.MSDULifeTime = msduLifeTime

        elif index == 3: #AC_VI
            self.AC_VI.EDCATable.CWmin = 2**ecwMin-1
            self.AC_VI.EDCATable.CWmax = 2**ecwMax-1
            self.AC_VI.EDCATable.AIFSN = aifsn
            self.AC_VI.EDCATable.TXOPLimit = txopLimit
            self.AC_VI.EDCATable.MSDULifeTime = msduLifeTime

        elif index == 4: #AC_VO
            self.AC_VO.EDCATable.CWmin = 2**ecwMin-1
            self.AC_VO.EDCATable.CWmax = 2**ecwMax-1
            self.AC_VO.EDCATable.AIFSN = aifsn
            self.AC_VO.EDCATable.TXOPLimit = txopLimit
            self.AC_VO.EDCATable.MSDULifeTime = msduLifeTime

        else:
            raise ValueError("Index Error for EDCATable.")
        
        
        
        
    def send(self, msdu, srcMACAddr, destMACAddr, priority, serviceClass):
        """
        This method (called only by the LCC layer) assembles a MAC data frame
        from the provided data (bitstream) as described
        in the standard, Section 7.2.2. It then calls the channel access
        method that tries to acquire the channel and transmit the frame.

        This operation is not buffered and can only have a single unicast frame
        in transmission. If it is called while the precedent frame has not yet
        complete transmission, an exception is raised.

        The upper layer is informed by dl.sendStatus when:
            - The ACK is received (satus: SUCCESS)
            - The max number of retransmission is reached (status: UNDELIVERABLE)
        
        Structure DCF of Transmission Queue: (tuple)
            - MSDU
            - Address 1
            - Address 2
            - Address 3
            
            
        Structure EDCA of Transmission Queue: (list)
            - MSDU ID
            - MSDU
            - Address 1
            - Address 2
            - Address 3
            - Priority
            - ServiceClass
            - Life Time Event
            
        
        @type msdu:             Bitstream (list of char)
        @param msdu:            MSDU to transmit
            
        @type srcMACAddr:       MAC address (String)
        @param srcMACAddr:      Source MAC address
            
        @type destMACAddr:      MAC address (String)
        @param destMACAddr:     Destination MAC address
            
        @type priority:         Integer
        @param priority:        Priority of Data (TID: 0-15). 0 = DCF.
            
        @type serviceClass:     Boolean
        @param serviceClass:    Service Class of Data (True = QoSAck, False = QoSNoAck)
        
        @rtype:                 None
        @return:                None
        """

        #Address management
        #For (Q)AP
        if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
        
            address1 = destMACAddr          #TX address
            address2 = self._bib.bssId      #RX address
            address3 = srcMACAddr
        
        #For (Q)STA
        else:
            if (srcMACAddr != self._mib.address):
                raise ValueError(self._niu._node.hostname 
                +": MAC Source Address proposed(%s) for the send of a new data frame" %srcMACAddr
                +" is not egal with MAC Address: " +self._mib.address)
        
            address1 = self._bib.bssId      #TX address
            address2 = srcMACAddr           #RX address
            address3 = destMACAddr
            
            
        #For QoS devices --> EDCA
        if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
            #Determine AC for this current MSDU
            if self._mode == "DCF":
                accessCategory = "DCF"
            elif priority == 0:
                accessCategory = "AC_BE"
            
            elif priority == 1 or priority == 2:
                accessCategory = "AC_BK"
                
            elif priority == 3 or priority == 4 or priority == 5:
                accessCategory = "AC_VI"
                
            elif priority == 6 or priority == 7:
                accessCategory = "AC_VO"
                
            else:
                #TID
                None
            
            #Add the MSDU life time
            #Increment the MSDU ID
            self._msduId = (self._msduId +1)%256 #ID from 0 to 255

            #Life time event
            #When the life time is time up (MSDU will be discarded).
            lifeTimeEvent = SCHEDULE(eval("self." +accessCategory).EDCATable.MSDULifeTime\
            * self._TIME_UNIT, self._discardMsdu, (self._msduId, accessCategory))
                
            #Add an list of information in last place in Transmission Queue
            eval("self." +accessCategory).transmissionQueue.append([self._msduId, msdu, address1, \
            address2, address3, priority, serviceClass, lifeTimeEvent])
            
            if self._niu.__class__ == QAP:
                #Update QAP queues informations for the HC
                if accessCategory == "AC_BE":
                    index=0
                elif accessCategory == "AC_BK":
                    index=1
                elif accessCategory == "AC_VI":
                    index=2
                elif accessCategory == "AC_VO":
                    index=3
                    
                self._hc.queueSize[self._bib.apAddr][index] = len(eval("self." +accessCategory).transmissionQueue)


            print "%f : " %TIME() +self._niu._node.hostname +" : New " +accessCategory +" MSDU %i" %self._msduId #debug
            
        #For non-QoS devices --> DCF
        else:
            #No Life Time for DCF
            #Add an tuple of information in last place in Transmission Queue
            self.DCF.transmissionQueue.append((msdu, address1, address2, address3))
            
        
        #Test if MAC is IDLE to transmit now
        if self._macState != self._state.IDLE:
            return
            
        #Test if no NAV is present to transmit now
        if self._navEventId:
            if self._macState != self._state.SEND_ACK:
                self._macState = self._state.IDLE
            return

        #The Transmission(s) queue(s) is obligatory empty (except the new MSDU)
        #because the MAC State is never IDLE if there are still MSDU in wait to send.
        #Initiate the transmission procedure with the selection of next MSDU.
        self._txInProgress = True
        print "%f : " %TIME() +self._niu._node.hostname +" : TX ON (send)" #debug
        self._selectNextMSDU()




    def sendStatus(self, status, bitstream):
        """
        This method is called from the phy layer, when a transmission
        previously initiated with PHY.send terminates.
        
        For data frame transmission:
        A retry Event is created for execute a retransmission if no ACK is receive before
        ACK timeout. The dl.sendStatus and the statistics update is called when the ACK
        is received (do in mac.receive).
        
        For ACK frame transmission:
            - Statistics update.
            - If we are in a another State before a reception of data and the send of a ACK, 
              we restore this previous state (WAIT_ACK or SEND_DATA during a Backoff procedure).

        For Beacon frame transmission:
        Statistics update

        The parameters "bitstream" and "status" are not used.

        @type bitstream:    Bitstream (list of char)
        @param bitstream:   Data transmitted

        @type status:       Integer
        @param status:      A 0 indicates success. Any other status indicates an error.
        
        @rtype:             None
        @return:            None
        """

        self._latestTransmitActivity = TIME()
       
        #The last frame sended is a Data frame
        if (self._macState == self._state.SEND_DATA):
            #MAC enter in the mode "wait an ACK"
            self._macState = self._state.WAIT_ACK
            
            #Cancel always the life time event in the first physical transmission
            lifeTimeEvent = eval("self." +self._backoffEntityTransmit).transmissionQueue[0][7]
            if lifeTimeEvent:
                CANCEL(lifeTimeEvent)
                eval("self." +self._backoffEntityTransmit).transmissionQueue[0][7] = None

            
            #Statistics update about an eventual previous retransmission
            if eval("self." +self._backoffEntityTransmit).shortRetryCount:
                self.stat.framesRetransmitted += 1
                self.stat.octetsTransmittedError += len(self._sendBuffer.data)
        
            #Process a retransmission if no ACK is received after ackTimeout
            #Canceled if an ACK frame is received before (do in mac.receive)
            self._retryEventId = SCHEDULE(self._ackTimeout * self._TIME_UNIT, self._retransmission)


        #The last frame sended is an Ack frame
        elif (self._macState == self._state.SEND_ACK):
            #Statistics update
            self.stat.ackTransmit += 1
            
            print "%f : " %TIME() +self._niu._node.hostname +" : RX OFF" #debug
            print " "
            
            
            #Test if we are in a NAV period
            if self._navEventId:
                #Continue the NAV
                self._macState = self._state.IDLE
                return
                
                
            #Restore the last State of MAC
            self._restoreMacState()
            
          
            if self._macState == self._state.SEND_DATA:
                #When the Ack frame was sended, there was in a backoff procedure for
                #the send of a data frame. Continue this last procedure...
                return #The PHY layer will call the mac.channelAccess()
                
            elif self._macState == self._state.WAIT_ACK:
                #When the Ack frame was sended, there was in wait of a ACK of a previous data frame.
                if not self._retryEventId:
                    #The retransmission event is raised during the ACK send
                    #Make the retransmission now
                    SCHEDULE(0.0, self._retransmission)
           
                #Wait the retransmission event
                return
            
            elif self._macState == self._state.IDLE:
                #We left the MAC sublayer
                self._terminMac()

                
            else:
                raise ValueError(self._niu._node.hostname +": ACK is sended, "
                +"but the state (%i) before the send is erroneous." %self._macState)
            
        
        #The last frame sended is a QoS CF-Poll
        elif (self._macState == self._state.SEND_CFPOLL):
        
            #Statistics update
            self.stat.cfPollTransmit += 1
            
            #@@@One poll autorised by CP
            self._poll = False
            
            #We left the MAC sublayer
            self._macState = self._state.IDLE
            self._terminMac()
        
        

        #The last frame sended is a Beacon frame
        elif (self._macState == self._state.SEND_BEACON):
        
            #Statistics update
            self.stat.beaconTransmit += 1
            
            #Restore the last State of MAC
            self._restoreMacState()
            
            if self._macState == self._state.SEND_DATA:
                #When the Beacon frame was sended, there was in a send data procedure.
                #Continue this last procedure.
                return #The PHY layer will call the mac.channelAccess()
                
            elif self._macState == self._state.WAIT_ACK:
                #When the Beacon frame was sended, there was in wait of a ACK of a previous data frame.
                if not self._retryEventId:
                    #The retransmission event is raised during the Beacon send
                    #Make the retransmission now
                    SCHEDULE(0.0, self._retransmission)
           
                #Wait the retransmission event
                return
            
            elif self._macState == self._state.IDLE:
                #We left the MAC sublayer
                self._terminMac()
                
                
            else:
                raise ValueError(self._niu._node.hostname +": Beacon is sended, "
                +"but the state (%i) before the send is erroneous." %self._macState)
        
        
        
        #The last frame sended is a CF-End
        elif (self._macState == self._state.SEND_CFEND):
        
            #Statistics update
            self.stat.cfEndTransmit += 1

            #We left the MAC sublayer
            self._macState = self._state.IDLE
            self._terminMac()
        
        
        
        #Other types of frames
        #Nothing is made
        
        
        
        
    def receive(self, bitstream):
        """
        Receive a bitstream from the PHY layer. The frame can contain payload
        data or acknowledgement. The MAC State controle are made in the methods:
            - _receiveData()
            - _receiveAck()
            - _receiveBeacon()
            - _receiveQosCfPoll()
            - _receiveQosCfEnd()
        
        Reception of a data frame:  - Check frame
                                    - Send an ACK
                                    - Pass to dl, and clean up.
        
        Reception of an ACK frame:  - Check frame
                                    - Inform dl, and clean up.
                                
                                
        @type bitstream:    Bitstream (list of char)
        @param bitstream:   Data received
        
        @rtype:             None
        @return:            None
        """
        
        self._latestReceiveActivity = TIME()
        
        #If the MAC sublayer was in a Backoff procedure stop it.
        if self._backoffEventId:
            CANCEL(self._backoffEventId)
            #Retrieve the remain Backoff
            self._endBackoff()
        #If the MAC sublayer was in a IFS period stop it.
        if self._IFSEventId:
            CANCEL(self._IFSEventId)
            self._IFSEventId = None
            
        
        #Retrieve the frameControl information
        fc = self.format.FrameControl()
        fc.fill(bitstream[0:1])

        #Data frame receive
        if (fc.type == self._frameType.DATA) and (fc.subType == self._frameSubType.DATA):

            self._receiveData(bitstream)
        
        #Ack frame receive
        elif (fc.type == self._frameType.CONTROL) and (fc.subType == self._frameSubType.ACK):
        
            self._receiveAck(bitstream)
            
        #QoS Cf-Poll frame receive    
        elif (fc.type == self._frameType.DATA) and (fc.subType == self._frameSubType.QOSCF_POLL):
        
            self._receiveQosCfPoll(bitstream)
            
        #Cf-End frame receive
        elif (fc.type == self._frameType.CONTROL) and (fc.subType == self._frameSubType.CF_END):
        
            self._receiveQosCfEnd(bitstream)
            
        #Beacon frame receive
        elif (fc.type == self._frameType.MANAGEMENT) and (fc.subType == self._frameSubType.BEACON):
        
            self._receiveBeacon(bitstream)
            
            
        #Other frame receive
        else:
            #It's also possible there is an error in the frame Control.
            #Control the FCS
            checksum = crc32(bitstream[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
            FCS = (ord(bitstream[-4:-3])<<24) + (ord(bitstream[-3:-2])<<16) + (ord(bitstream[-2:-1])<<8) + ord(bitstream[-1:])
            if (checksum == FCS):
                raise ValueError(self._niu._node.hostname +": Frame format received is not implemented.")

            #Statistics updates, impossible to determine frame type due to an error in the header of frame
            self.stat.unknowReceivedFCSErrors += 1


            
            
    def channelIdle(self):
        """
        This method is called by PHY as soon as the channel becomes idle after a activity.
        Continue or restart a transmision if there is no NAV period.
       
        @rtype:     None
        @return:    None
        """
        
        #If there is a NAV period, no channel access is possible
        if self._navEventId:
            if self._macState != self._state.SEND_ACK:
                self._macState = self._state.IDLE
            return
        
        #Test if a transmission is waiting for idle channel and call it.
        if self._txInProgress and self._macState == self._state.SEND_DATA and not self._txop and not self._cap:
            self._startProcedureTime = TIME()
            SCHEDULE(0.0, self._channelAccess)
            return
            
        #TXOP polling by the QAP
        if self._mode == "HCCA":
            if self._niu.__class__ == QAP and (self._poll or self._cfp):
                self._selectSTAPoll()
            
            
        #If the Mac was Idle before the last activity and the transmission queue 
        #is not empty, select the next MSDU to proceed to a new transmission.
        if (self._macState == self._state.IDLE and self._txContinue()):
            print "%f : " %TIME() +self._niu._node.hostname +" : TX ON (channelIdle)" #debug
            self._txInProgress = True
            SCHEDULE(0.0, self._selectNextMSDU)

            
            
    def getMacAddr(self):
        """
        This method return the MAC address.

        @rtype:     MAC address (String)
        @return:    MAC address of this NIU
        """
        
        return self._mib.address
               
        
        
    # ------------------------ Private Methods ---------------------------- #

    def _channelAccess(self):
        """
        Try to have the access to the channel. Five stages are defined:
            1. Carrier Sense (PHY & MAC)
            2. Interframe space
            3. Backoff procedure (Optionnal)
            4. TBTT Procedure Control
            5. Phy sending
        
        This method is called:
            - For send procedure (data, ack, beacon)
            - For retransmision procedure
            - When we wait for Idle channel: by channelIdle()
            - By the Scheduler at the end of IFS or Backoff wait time
            
        The stages are executed everytime since the beginning.
        
        Backoff procedure (Collision Avoidance) is applicated when:
            - The MAC sublayer was busy when a demand of transmission by LLC sublayer was made
            - The channel was busy when the demand of transmission was made
            - After a retransmission failure
            
        @rtype:     None
        @return:    None
        """
        
        #Begin the transmit procedure only if the MAC sublayer is in a Send Mode
        if (self._macState != self._state.SEND_DATA) and (self._macState != self._state.SEND_ACK) \
        and (self._macState != self._state.SEND_BEACON) and (self._macState != self._state.SEND_CFPOLL) \
        and (self._macState != self._state.SEND_CFEND):
            raise ValueError(self._niu._node.hostname +": Want to access to the channel, "
            +"but there is no frame to send.")
        
        
        # 1. Carrier Sense (PHY & MAC)
        #print "%f : " %TIME() +self._niu._node.hostname +" : Want a Channel Access. State: " +str(self._macState) #debug
        if self._navEventId and self._macState != self._state.SEND_ACK:
            #If it is a NAV period, no channel access is possible (except for a ACK send)
            self._macState = self._state.IDLE
            #Case of the IFS period end and the channel is NAV
            self._IFSEventId = None
            return
        if self._niu.phy.carrierSense():
            #Case of the IFS period finish and the channel is busy
            self._IFSEventId = None
        
            #The channel is busy
            if self._macState == self._state.SEND_ACK:
                raise ValueError(self._niu._node.hostname +": The ACK frame could not be sended, "
                +"the channel is busy.")

            elif self._macState == self._state.SEND_BEACON:
                raise ValueError(self._niu._node.hostname +": The Beacon frame could not be sended, "
                +"the channel is busy.")
            
            elif self._macState == self._state.SEND_DATA:
                #Wait until channel activities end (a Backoff procedure will be applied). 
                #The mac.channelIdle method will call by PHY when the channel will be free.
                self._applyBackoff = True
                return
                
            elif self._macState == self._state.SEND_CFPOLL:
                raise ValueError(self._niu._node.hostname +": The QoS CF-Poll frame could not be sended, "
                +"the channel is busy.")
                
            elif self._macState == self._state.SEND_CFEND:
                raise ValueError(self._niu._node.hostname +": The CF-End frame could not be sended, "
                +"the channel is busy.")
                
            else:
                raise ValueError(self._niu._node.hostname +": Want to access to the channel, " 
                +"but there is no frame to send.")


        # 2. Interframe Space
        if self._IFS():
            #Wait until the Scheduler called this _channelAccess() Method
            return
        

        # 3. Backoff procedure (Collision Avoidance)
        if self._backoff():
            #Wait until the Scheduler called this _channelAccess() Method
            return
    
    
        # 4. Report the transmission if the next TBTT is encroached by the total procedure of transmission.
        # For DATA frame: DATA + 2xSIFS + ACK. The second SIFS is for the Beacon in TBTT
        if self._beacon and self._macState == self._state.SEND_DATA:
            if TIME() + self._niu.phy.getTransmissionTime(len(self._sendBuffer.serialize()))\
            + self._niu.phy.getTransmissionTime(self._ACKSIZE) + 2*self._niu.phy.computeIFS()[0] > self._targetBeaconTxTime:
            
                if self._txop:
                    raise ValueError(self._niu._node.hostname +": Want to access to the channel in a TXOP"
                    +" but TBTT will be encroached (Test must be made in method ReceiveACK)")

                else:
                    #It's the first frame (TXOP or CAP) or there is no TXOP
                    #The transmission is reported after the reception of beacon
                    #will be recalled by mac.channelIdle()
                    self._applyBackoff = True
                    if self._cap:
                        self._cap = False
                    print "%f : " %TIME() +self._niu._node.hostname +" : The transmission is reported after the reception of beacon."\
                    +" TBTT: %f (Data transmission)" %self._targetBeaconTxTime#@@debug

                    return
                    
        # For QoS CF-Poll frame: CF-POLL + SIFS. 
        elif self._beacon and self._macState == self._state.SEND_CFPOLL:
            if TIME() + self._niu.phy.getTransmissionTime(len(self._sendBuffer.serialize()))\
            + self._niu.phy.computeIFS()[0] > self._targetBeaconTxTime:
                #The send of QoS CF-Poll frame is canceled
                self._poll = False
                self._macState = self._state.IDLE
                self._terminMac()
                return
    
    
        # 5. Initiate the transmission
        #@@debug
        if self._macState == self._state.SEND_DATA:
            if (eval("self." +self._backoffEntityTransmit).shortRetryCount > 0):
                print "%f : " %TIME() +self._niu._node.hostname +" : Data Retransmission"
                ACTIVITY_INDICATION(self, "tx", "data retransmission", "red", 3, 2)
            else:
                print "%f : " %TIME() +self._niu._node.hostname +" : Send Data"
                ACTIVITY_INDICATION(self, "tx", "data", "green", 0, 0)
        elif self._macState == self._state.SEND_ACK:
            print "%f : " %TIME() +self._niu._node.hostname +" : Send Ack"
            ACTIVITY_INDICATION(self, "tx", "ack", "blue", 3, 2)
        elif self._macState == self._state.SEND_BEACON:
            print "%f : " %TIME() +self._niu._node.hostname +" : Send Beacon"
            if self._cfp:
                print "%f : " %TIME() +self._niu._node.hostname +" : START CFP"
            ACTIVITY_INDICATION(self, "tx", "darkblue", "", 3, 2)
        elif self._macState == self._state.SEND_CFPOLL:
            print "%f : " %TIME() +self._niu._node.hostname +" : Send QoS CF-Poll"
            ACTIVITY_INDICATION(self, "tx", "darkblue", "", 3, 2)  
        elif self._macState == self._state.SEND_CFEND:
            print "%f : " %TIME() +self._niu._node.hostname +" : Send QoS CF-End"
            print "%f : " %TIME() +self._niu._node.hostname +" : STOP CFP"
            ACTIVITY_INDICATION(self, "tx", "darkblue", "", 3, 2)
        else:
            print "%f : " %TIME() +self._niu._node.hostname + " : %i"  %self._macState
        
        self._latestStartTransmitActivity = TIME()
        self._niu.phy.send(self._sendBuffer.serialize())
        
        
        
        
    def _IFS(self):
        """
        Decide if IFS must be applied. If yes, wait SIFS, PIFS, AIFS(DIFS) or EIFS
        in function of the informations to send.
        
        @rtype:     Boolean
        @return:    True if IFS must be applied.
        """
        
                
        if self._startProcedureTime == TIME():
                
            #Obtain the IFS
            SIFS, PIFS, DIFS, EIFS = self._niu.phy.computeIFS()
            
            #Select the appropriate IFS
            if (self._macState == self._state.SEND_ACK):
                IFS = SIFS
                self._applyBackoff = False #No Backoff is applied
                    
            elif (self._macState == self._state.SEND_BEACON):
                self._applyBackoff = False #No Backoff is applied
                #A SIFS Time is already garanted before the send of beacon
                return False
                
            elif (self._macState == self._state.SEND_DATA):
                if self._txop or self._cap:
                    IFS = SIFS
                else:
                    #QoS devices
                    if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
                        AIFS = self._niu.phy.computeIFS(eval("self." +self._backoffEntityTransmit).EDCATable.AIFSN)[2]
                        if self._lastFrameError:
                            IFS = EIFS - DIFS + AIFS #ref: 9.2.3.5
                        else:
                            IFS = AIFS
            
                    #Non-QoS devices
                    else:
                        if self._lastFrameError:
                            IFS = EIFS #ref: 9.2.3.5
                        else:
                            IFS = DIFS
                            
            elif (self._macState == self._state.SEND_CFPOLL):
                IFS = PIFS
                self._applyBackoff = False #No Backoff is applied
                
            else:
                IFS = DIFS
            
            
            #Respect the TBTT
            if self._beacon:
                if TIME() + IFS > self._targetBeaconTxTime:
                    if self._txop:
                        raise ValueError(self._niu._node.hostname +": Want to access to the channel in a TXOP"
                        +" but TBTT will be encroached (Test must be made in method ReceiveACK)")
                    else:
                        if self._macState == self._state.SEND_DATA:
                            #The transmission is reported after the reception of beacon
                            #will be recalled by mac.channelIdle()
                            self._applyBackoff = True
                            if self._cap:
                                self._cap = False
                            print "%f : " %TIME() +self._niu._node.hostname +": The transmission is reported after the reception of beacon. TBTT: %f (IFS)"\
                            %self._targetBeaconTxTime #@@debug
                        elif self._macState == self._state.SEND_CFPOLL:
                            #The transmission is canceled
                            self._poll = False
                            self._macState = self._state.IDLE
                            self._terminMac()

                        return True
            
            
            #Wait the IFS
            print "%f : " %TIME() +self._niu._node.hostname +" : IFS: %f" %IFS #debug
            self._IFSEventId = SCHEDULE(IFS, self._channelAccess)

            return True
        
        else:

            #The IFS was already waited
            self._IFSEventId = None
            return False
            
            
            
    def _saveMacState(self):
        """
        The present State of MAC is saved, because an higher priority operation must be made.
        That will allow to continue the actual activities after the end of higher priority 
        operation to restore this state with _restoreMacState() method.
        
        This method is used:
            - When a data is received during Backoff procedure or during a wait ACK of a 
              previous send of a data frame. A ACK must be sended.
            - When a Beacon must be sended.

        @rtype:     None
        @return:    None
        """
        
        #Save the actual State of MAC sublayer
        self._macSave['lastMacState'] = self._macState
        #Save the actual send Buffer
        self._macSave['lastSendBuffer'] = self._sendBuffer
        
        
        
    def _restoreMacState(self):
        """
        Restore the previous state of MAC if the _saveMacState() method has be used before
        the execution of an higher priority operation. Don't restore if the state of 
        MAC sublayer was IDLE.

        @rtype:     None
        @return:    None
        """

        #Restore the last State of MAC sublayer
        self._macState = self._macSave['lastMacState']
        #Restore the last send Buffer
        if self._macSave['lastSendBuffer']:
            self._sendBuffer = self._macSave['lastSendBuffer']
            
        #If there is a transmission in progress, apply a Backoff    
        if self._txInProgress:
            self._applyBackoff = True
        
        
        
    def _txContinue(self):
        """
        Test if another MSDU is present in transmissions queue
        to continue to transmit.
    
        @rtype:     Boolean
        @return:    True if the transmission must be continued. Else False.
        """
    
        #QoS entity
        if (self._niu.__class__ == QWNIC or self._niu.__class__ == QAP):
    
            if self.AC_BK.transmissionQueue or self.AC_BE.transmissionQueue or \
            self.AC_VI.transmissionQueue or self.AC_VO.transmissionQueue:
                self._applyBackoff = True #To applying Backoff
                return True
            return False
    
        #Non-QoS entity
        else:
            if self.DCF.transmissionQueue:
                self._applyBackoff = True #To applying Backoff
                return True
            return False



    def _newTBTT(self):
        """
        Set a new TBTT when the Beacon Interval has changed or 
        for the first TBTT. The TBTT cooresponds always a multiple
        of TU.
        
        @rtype:     None
        @return:    None
        """
        #Set the new TBTT value
        self._targetBeaconTxTime = self._niu.phy.getTimeLastReceiveActivity()\
        + self._bib.beaconInterval*self._TIME_UNIT
        
        if self._beaconEventId:
            #Cancel the actual TBTT event
            CANCEL(self._beaconEventId)
        
        print "%f : " %TIME() +self._niu._node.hostname +" : next TBTT = %f" %self._targetBeaconTxTime #debug
        
        #Set the next TBTT by event
        if self._beacon:
            self._beaconEventId = SCHEDULEABS(self._targetBeaconTxTime, self._setTBTT)
    
    
    def _setTBTT(self):
        """
        Set the TBTT every Beacon Interval by event. This method is not use
        by the AP. AP use the method _sendBeacon() to set TBTT.
        
        @rtype:     None
        @return:    None
        """
        #Set the next TBTT value
        self._targetBeaconTxTime = TIME() + self._bib.beaconInterval*self._TIME_UNIT
        
        print "%f : " %TIME() +self._niu._node.hostname +" : next TBTT = %f" %self._targetBeaconTxTime #debug
        
        #Called again this same method to set the next TBTT
        if self._beacon:
            self._beaconEventId = SCHEDULEABS(self._targetBeaconTxTime, self._setTBTT)



    def _setNAV(self, lengthNAV):
        """
        The period of Network Allocation Vector is started or updated.
        The MAC state is set to IDLE. If the parameter lengthNAV is 0,
        the period of MAC is applied but the length is unspecified. Wait a
        endNAV to finish the NAV.
       
        @type lengthNAV:   Float
        @param lengthNAV:  length of NAV in second
        
        @rtype:         None
        @return:        None
        """
        if not self._navEventId:
            #Start the NAV
            self._saveMacState()
            print "%f : " %TIME() +self._niu._node.hostname +" : NEW NAV to %f" %(TIME()+lengthNAV) #debug
            
            if lengthNAV == 0:
                #The period of NAV is unspecified
                self._navEventId = 1


        else:
            #Update the NAV
            CANCEL(self._navEventId)
            if TIME() + lengthNAV < self._navEventId[0] - 3*self._MIN_UNIT or TIME() + lengthNAV > self._navEventId[0] + 3*self._MIN_UNIT:
                print "%f : " %TIME() +self._niu._node.hostname +" : NAV update to %f" %(TIME()+lengthNAV) #debug
        
        
        #Control than the NAV finish before the TBTT
        timeRemainToTBTT = self._targetBeaconTxTime - TIME() - self._niu.phy.computeIFS()[0]
        if timeRemainToTBTT < lengthNAV:
            self._navEventId = SCHEDULE(timeRemainToTBTT, self._endNAV)
        else:
            self._navEventId = SCHEDULE(lengthNAV + self._MIN_UNIT, self._endNAV)
            
        self._macState = self._state.IDLE
        
        #Cancel IFS Event
        if self._IFSEventId:
            CANCEL(self._IFSEventId)
            self._IFSEventId = None
        

      

      
    def _endNAV(self):
        """
        The Network Allocation Vector is finished.
        Restore the MAC state and continue the work before the NAV period.
        
        @rtype:     None
        @return:    None
        """
        
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_BEACON:
            raise ValueError(self._niu._node.hostname  +": Not possible to end the NAV."
            +" The state of MAC is %i." %self._macState)
        
        print "%f : " %TIME() +self._niu._node.hostname +" : End of NAV"
        
        self._navEventId = None
        
        self._restoreMacState()
        
        if self._macState == self._state.SEND_DATA:
            #When the NAV period frame was started, there was in a backoff procedure for
            #the send of a data frame. Continue this last procedure...
            self.channelIdle()
                
        elif self._macState == self._state.WAIT_ACK:
            #When the NAV period frame was started, there was in wait of a ACK of a previous data frame.
            if not self._retryEventId:
                #The retransmission event is raised during the NAV period
                #Make the retransmission now
                self._retransmission()
       
            #Wait the retransmission event
            return
        
        elif self._macState == self._state.IDLE:
            #We left the MAC sublayer
            self._terminMac()
        
        
        
        
        
    def _terminMac(self):
        """
        The method is executed everytime that the MAC sublayer is left after
        a transmission (not after a reception). The privates variables is initialized
        for the next transmission and the LLC sublayer is informed of the liberation
        of MAC sublayer.
        
        @rtype:     None
        @return:    None
        """
        
        if self._macState != self._state.IDLE and self._macState != self._state.WAIT_ACK:
            raise ValueError(self._niu._node.hostname  +": Not possible to cloture a MAC action now."
            +" The state of MAC is %i." %self._macState)
        
        
        #Initialize the privates variables for the next transmission
        if self._backoffEntityTransmit == "DCF":
            self.DCF.shortRetryCount = 0
            self.DCF.remainBackoffCTR = 0
          
        elif self._backoffEntityTransmit == "AC_BK":
            self.AC_BK.shortRetryCount = 0
            self.AC_BK.remainBackoffCTR = 0
            
        elif self._backoffEntityTransmit == "AC_BE":
            self.AC_BE.shortRetryCount = 0
            self.AC_BE.remainBackoffCTR = 0
            
        elif self._backoffEntityTransmit == "AC_VI":
            self.AC_VI.shortRetryCount = 0
            self.AC_VI.remainBackoffCTR = 0
             
        elif self._backoffEntityTransmit == "AC_VO":
            self.AC_VO.shortRetryCount = 0
            self.AC_VO.remainBackoffCTR = 0
            
        self._sendBuffer = None
        self._backoffEntityTransmit = None
        self._applyBackoff = False
        self._macState = self._state.IDLE
        
        self._macSave= {"lastMacState": self._state.IDLE,
                              "lastSendBuffer": None}
        
        #Cancel the Mac Events
        if self._retryEventId:
            CANCEL(self._retryEventId)
            self._retryEventId = None
        if self._backoffEventId:
            CANCEL(self._backoffEventId)
            self._backoffEventId = None
        if self._IFSEventId:
            CANCEL(self._IFSEventId)
            self._IFSEventId = None
        
        #The MAC sublayer is now idle.


    
    
    # ------------------------ Send Methods ---------------------------- #
 
    def _selectNextMSDU(self):
        """
        Choose the next MSDU to send.
            - DCF: Take the next in the transmission queue.
            - EDCA: Virtual contention between the four Backoff Entities.
                    The prioritest Backoff entity will initiate the transmission.
                    
        @rtype:     None
        @return:    None
        """
            
        #For QoS devices --> EDCA
        if (self._niu.__class__ == QAP or self._niu.__class__ == QWNIC):
            
            #Make virtual contention with internal passive Backoff
            #between the 4 Backoff entities. Use the remain Backoff if there is one.
            #Attribue the lowest priority fot the empty transmission queue.
            lowestPriority = self.AC_BK.EDCATable.AIFSN + self.AC_BK.EDCATable.CWmax
            
            if self.AC_BK.transmissionQueue:
                if self.AC_BK.remainBackoffCTR > 0:
                    AC_BKBackoff = self._computeBackoff("AC_BK")
                else:
                    AC_BKBackoff = self.AC_BK.remainBackoffCTR
            else:
                AC_BKBackoff = lowestPriority
                
            if self.AC_BE.transmissionQueue:
                if self.AC_BE.remainBackoffCTR > 0:
                    AC_BEBackoff = self._computeBackoff("AC_BE")
                else:
                    AC_BEBackoff = self.AC_BE.remainBackoffCTR
            else:
                AC_BEBackoff = lowestPriority
              
            if self.AC_VO.transmissionQueue:
                if self.AC_VO.remainBackoffCTR > 0:
                    AC_VOBackoff = self._computeBackoff("AC_VO")
                else:
                    AC_VOBackoff = self.AC_VO.remainBackoffCTR
            else:
                AC_VOBackoff = lowestPriority
             
            if self.AC_VI.transmissionQueue:
                if self.AC_VI.remainBackoffCTR > 0:
                    AC_VIBackoff = self._computeBackoff("AC_VI")
                else:
                    AC_VIBackoff = self.AC_VI.remainBackoffCTR
            else:
                AC_VIBackoff = lowestPriority
             
            
            #AC_XXpriority is not time value, only indicative value
            AC_BKpriority = self.AC_BK.EDCATable.AIFSN + AC_BKBackoff
            AC_BEpriority = self.AC_BE.EDCATable.AIFSN + AC_BEBackoff
            AC_VIpriority = self.AC_VI.EDCATable.AIFSN + AC_VIBackoff
            AC_VOpriority = self.AC_VO.EDCATable.AIFSN + AC_VOBackoff
            
            
            #Test if internal collision is present
            priorityDic = {"AC_VO": AC_VOpriority, "AC_VI": AC_VIpriority, "AC_BE": AC_BEpriority, "AC_BK": AC_BKpriority}
            highestPriority = min(priorityDic.values())
            if priorityDic.values().count(highestPriority) > 1:
                #Internal Collision
                print "%f : " %TIME() +self._niu._node.hostname +" : Internal Collision !!" #debug
                #Update the Retry Count for the collisioned Backoff Entity
                for item in priorityDic.items():
                    if item[1] == highestPriority:
						eval("self." +item[0]).shortRetryCount += 1

            #The win AC of virtual contention
            #If there is an internal collision it's the most priority is taken
            #AC_VO ==> AC_VI ==> AC_BE ==> AC_BK
            winAC = priorityDic.items()[priorityDic.values().index(highestPriority)][0]
            
            #Use the compute Backoff to apply the real wait. Set this like a remain Backoff.
            self._backoffEntityTransmit = winAC
            eval("self." + winAC).remainBackoffCTR = eval(winAC +"Backoff")
            
            #Update the remain Backoff of the loser Backoff Entities
            if self.AC_BK.transmissionQueue and AC_BK != winAC:
                self.AC_BK.remainBackoffCTR = self.AC_BK.remainBackoffCTR - eval(winAC +"Backoff")
                if self.AC_BK.remainBackoffCTR < 0:
                    self.AC_BK.remainBackoffCTR = 1
                
            if self.AC_BE.transmissionQueue:
                self.AC_BE.remainBackoffCTR = self.AC_BE.remainBackoffCTR - eval(winAC +"Backoff")
                if self.AC_BE.remainBackoffCTR < 0:
                    self.AC_BE.remainBackoffCTR = 1
                
            if self.AC_VO.transmissionQueue:
                self.AC_VO.remainBackoffCTR = self.AC_VO.remainBackoffCTR - eval(winAC +"Backoff")
                if self.AC_VO.remainBackoffCTR < 0:
                    self.AC_VO.remainBackoffCTR = 1
                
            if self.AC_VI.transmissionQueue:
                self.AC_VI.remainBackoffCTR = self.AC_VI.remainBackoffCTR - eval(winAC +"Backoff")
                if self.AC_VI.remainBackoffCTR < 0:
                    self.AC_VI.remainBackoffCTR = 1
             
            self._backoffEntityTransmit = winAC
            
        #For non-QoS devices --> DCF
        else:
            self._backoffEntityTransmit = "DCF"
        

        lifeTimeEvent = eval("self." +self._backoffEntityTransmit).transmissionQueue[0][7]
        print "%f : " %TIME() +self._niu._node.hostname +" : Select " +self._backoffEntityTransmit +" MSDU %i to send" %lifeTimeEvent[3] [0] #debug
            
            
        #Construct and send the new frame
        self._sendData()
    
    
    
    def _selectSTAPoll(self):
        """
        In HCCA mode, select the QSTA to poll. This selection is for a CFP or a CP period.
        
        @rtype:     None
        @return:    None
        """
        
        #Send a poll only if the MAC state is IDLE
        if self._macState != self._state.IDLE:
            return
        
        if self._cfp:
            #Contention Free Period (CFP)
            
            #Control the remain CFP
            if TIME() > self._endCfpMax:
                #have a larger marge: @@@TODO
                return
           
            #Choice the prioritest AC in the QBSS
            (addrQsta, tid) = self._hc.selectAC()
            
            if not addrQsta:
                raise ValueError(self._niu._node.hostname  +": Not possible to select a QSTA to do a Poll.")
            
        else:
            #Contention Period (CP)
            #Scan one by one the QSTA in BSS @@@todo
            
            #@@@ Unique address for the moment
            addrQsta = self._bib.staAddr[3]
            tid = 0 #It's the QSTA that choice the AC
        
        
        self._sendQosCfPoll(addrQsta, tid)
    
    
        
    
    def _sendData(self):
        """
        Construct the Data frame and access to the channel to send it.
        AP to AP through DS or STA to STA in iBSS are not implemented.
        Fragmentation not implemented.
        
        @rtype:     None
        @return:    None
        """

        #The state of MAC must be IDLE to make the transmission
        if self._macState != self._state.IDLE:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the Data frame."
            +" The state of MAC is %i." %self._macState)
            

        #No transmission is started if NAV period is active
        if self._navEventId:
            if self._macState != self._state.SEND_ACK:
                self._macState = self._state.IDLE
            self._retryEventId = None
            return
        
        #Make sure there is no other packet already in transmit.
        assert(not self._sendBuffer)
        
        self._macState = self._state.SEND_DATA
        
        #Obtain the informations of the current data frame
        msduId, msdu, address1, address2, address3, priority, serviceClass, lifeTimeEvent = \
        eval("self." +self._backoffEntityTransmit).transmissionQueue[0]
        
        
        #Test the size of MSDU
        if (len(msdu) > self._MAX_MSDUSIZE):
            raise ValueError(self._niu._node.hostname +": The MSDU of the futur sended data is too large"
            +"(max: %i octets)" %self._MAX_MSDUSIZE)
        
        
        #Construct the MPDU
        frame = self.MPDUFormat()
        
        #FRAME CONTROL FIELD
        fc = self.format.FrameControl()
        #Type and subtype
        fc.type = self._frameType.DATA
        fc.subType = self._frameSubType.DATA
        #toDS and fromDS bits
        if (self._niu.__class__ == AP) or (self._niu.__class__ == QAP):
            #(Q)AP to (Q)STA
            fc.toDS = 0
            fc.fromDS = 1
        else:
            #(Q)STA to (Q)AP
            fc.toDS = 1
            fc.fromDS = 0
        #Retry bit
        if (eval("self." +self._backoffEntityTransmit).shortRetryCount == 0):
            fc.retry = 0
        else:
            fc.retry = 1
        frame.frameControl = fc.serialize()
    
                
        #DURATION ID FIELD (to set the NAV)
        if not eval("self." +self._backoffEntityTransmit).EDCATable.TXOPLimit and not self._cap:
            #EDCA TXOP One Frame Transmission
            frame.durationID = 0
        else:
            remainTXdata = 0.0
            #First frame of EDCA TXOP Multiple Frame Transmission
            if not self._txop and not self._cap:
                if len(eval("self." +self._backoffEntityTransmit).transmissionQueue) > 1:
                    #If there is many frames in transmission queue
                    #Duration ID value (Ref 7.1.4)
                    for record in eval("self." +self._backoffEntityTransmit).transmissionQueue:
                        msdu = record[1]
                        nextTxDuration = self._niu.phy.getTransmissionTime(len(msdu)+self._DATAHEADER) \
                        + self._niu.phy.getTransmissionTime(self._ACKSIZE) + 2*self._niu.phy.computeIFS()[0]
                        if remainTXdata + nextTxDuration < eval("self." +self._backoffEntityTransmit).EDCATable.TXOPLimit*1e-6:
                            remainTXdata = remainTXdata + nextTxDuration
                        else:
                            #DurationId is fixed with max TXOP (TXOP limit)
                            remainTXdata = eval("self." +self._backoffEntityTransmit).EDCATable.TXOPLimit*1e-6
                            break
                            
                #If there is only one frame in transmission queue, the TXOP is not set (= 0) ==> No NAV applied
                  
            else:
                #EDCA TXOP Multiple Frame Transmission or CAP
                #Duration ID value (Ref 7.1.4)
                for record in eval("self." +self._backoffEntityTransmit).transmissionQueue:
                    msdu = record[1]
                    nextTxDuration = self._niu.phy.getTransmissionTime(len(msdu)+self._DATAHEADER) \
                    + self._niu.phy.getTransmissionTime(self._ACKSIZE) + 2*self._niu.phy.computeIFS()[0]
                    if  remainTXdata + nextTxDuration < self._remainTXOP:
                        remainTXdata = remainTXdata + nextTxDuration
                    else: 
                        break
            
                if remainTXdata == 0.0 and not self._cap:
                    raise ValueError(self._niu._node.hostname  +": Error in TXOP compute.")
                    
                    
            if remainTXdata != 0.0:
                #The time of actual send procedure (SIFS + data) is soustracted for the Duration ID field
                remainTXdata = remainTXdata - \
                self._niu.phy.getTransmissionTime(len(eval("self." +self._backoffEntityTransmit).transmissionQueue[0][1])+self._DATAHEADER)\
                - self._niu.phy.computeIFS()[0]

            frame.durationID = int(remainTXdata*1e6)
            
        print "%f : " %TIME() +self._niu._node.hostname +" : Duration ID = %i us" %frame.durationID #debugg
                
        
        
        #ADDRESS FIELDS
        frame.address1 = address1
        frame.address2 = address2
        frame.address3 = address3
        
        #SEQUENCE CONTROL FIELD
        sc = self.format.SequenceControl()
        sc.fragmentNb = 0
        #Increment the sequence number (if it's not a phy retransmission)
        if not self._retryEventId:
            self._sequenceNb = (self._sequenceNb +1)%4096 #Count from 0 to 4095
        self._retryEventId = None
        sc.sequenceNb = self._sequenceNb
        frame.sequenceControl = sc.serialize()
        
        #QOS CONTROL FIELD
        if (self._niu.__class__ == QWNIC or self._niu.__class__ == QAP):
            qc = self.format.QosControl()
        
            #Priority
            qc.tid = priority

            #Service Class
            qc.ackPolicy = serviceClass
            
            #Give the information about the size of transmission queue of this current AC
            #EOSP
            qc.eosp = 1
            qc.txopOrQueue = len(eval("self." +self._backoffEntityTransmit).transmissionQueue)
            
            frame.qosControl = qc.serialize()
            
            
        #DATA FIELD
        frame.data = msdu
        
        #FRAME CHECK SEQUENCE FIELD
        checksum = crc32(frame.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        frame.FCS = checksum
    
        self._sendBuffer = frame
        self._startProcedureTime = TIME()
        self._channelAccess()
        
        
        
    def _sendQosCfPoll(self, destMACAddr, tid):
        """
        Construct a QoS CF-POLL frame and access to the channel to send it.
        
        
        @type destMACAddr:  String
        @param destMACAddr: MAC address of the QSTA where the poll will be send 
        
        @type tid:          Integer
        @param tid:         The TID selected (correspond to ACs) 
        
        @rtype:             None
        @return:            None
        """
        
        #Send only by QAP
        if self._niu.__class__ != QAP:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the QoS CF-Poll frame."
            +"The entity must be a QAP.")
        
        #Send only in the HCCA mode
        if self._mode != "HCCA":
            raise ValueError(self._niu._node.hostname  +": Not possible to send the QoS CF-Poll frame."
            +"The mode must be HCCA.")
        
        #The state of MAC must be IDLE to make this transmission
        if self._macState != self._state.IDLE:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the QoS CF-Poll frame."
            +"The state of MAC is %i." %self._macState)
            

        #No transmission is started if NAV period is active
        if self._navEventId:
            if self._macState != self._state.SEND_ACK:
                self._macState = self._state.IDLE
            self._retryEventId = None
            return
        
        #Make sure there is no other packet already in transmit.
        assert(not self._sendBuffer)
        
        self._macState = self._state.SEND_CFPOLL
        
        
        #Construct the MPDU
        frame = self.MPDUFormat()
        
        #FRAME CONTROL FIELD
        fc = self.format.FrameControl()
        #Type and subtype
        fc.type = self._frameType.DATA
        fc.subType = self._frameSubType.QOSCF_POLL
        #toDS and fromDS bits
        #(Q)AP to (Q)STA
        fc.toDS = 0
        fc.fromDS = 1
        #Retry bit
        fc.retry = 0
        frame.frameControl = fc.serialize()
    
                
        #DURATION ID FIELD (to set the NAV)
        frame.durationID = 0

        #ADDRESS FIELDS
        frame.address1 = destMACAddr          #TX address
        frame.address2 = self._bib.bssId      #RX address
        frame.address3 = self._bib.apAddr
        
        #SEQUENCE CONTROL FIELD
        sc = self.format.SequenceControl()
        sc.fragmentNb = 0
        #Increment the sequence number (if it's not a phy retransmission)
        if not self._retryEventId:
            self._sequenceNb = (self._sequenceNb +1)%4096 #Count from 0 to 4095
        self._retryEventId = None
        sc.sequenceNb = self._sequenceNb
        frame.sequenceControl = sc.serialize()
        
        #QOS CONTROL FIELD
        qc = self.format.QosControl()
        #Priority
        qc.tid = tid
        #Service Class
        qc.ackPolicy = 0 #Normal acknowledgment
        #Proposed TXOP (unit: 32 us)
        qc.txopOrQueue = 100 #determined by the HC @@@todo
        frame.qosControl = qc.serialize()

        #DATA FIELD
        None
        
        #FRAME CHECK SEQUENCE FIELD
        checksum = crc32(frame.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        frame.FCS = checksum
    
        self._sendBuffer = frame
        self._startProcedureTime = TIME()
        self._channelAccess()

        
        
        
    def _sendCfEnd(self):
        """
        Construct a CF-End frame to end the Contention Free Period. 
        Access to the channel to send it.
        
        @rtype:     None
        @return:    None
        """
        #Send only by QAP
        if self._niu.__class__ != QAP:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the CF-End frame."
            +"The entity must be a QAP.")
        
        #Send only in the HCCA mode
        if self._mode != "HCCA":
            raise ValueError(self._niu._node.hostname  +": Not possible to send the CF-End frame."
            +"The mode must be HCCA.")
        
        #The state of MAC must be IDLE to make this transmission
        if self._macState != self._state.IDLE:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the CF-End frame."
            +"The state of MAC is %i." %self._macState)
        
        #Construct CF-END frame
        cfEnd = self.format.CF_END()
        
        #FRAME CONTROL FIELD
        fc = self.format.FrameControl()
        fc.type = self._frameType.CONTROL
        fc.subType = self._frameSubType.ACK
        fc.toDS = 0 #toDS and fromDS bits (always set to 0 for control frame)
        fc.fromDS = 0
        cfEnd.frameControl = fc.serialize()

        #DURATION ID FIELD
        cfEnd.durationID = 0 #to set the NAV. Not employed.

        #ADDRESS FIELD
        cfEnd.receiverAddress = "FF:FF:FF:FF:FF:FF" #Broadcast
        cfEnd.BSSID = self._bib.bssId

        #FRAME CHECK SEQUENCE FIELD
        checksum = crc32(cfEnd.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        cfEnd.FCS = checksum

        self._sendBuffer = cfEnd
        self._applyBackoff = False
        
        #Access to the channel
        self._startProcedureTime = TIME()
        self._channelAccess()
        
        
        
               
    def _sendBeacon(self):
        """
        Manage the regular sending of Beacons when the Beacon Management was enabled
        by the method _startbeacon(). This method can be called only by an (Q)AP.
        
        In the EDCA Parameter Set:
        
        ACI:    AC:          Access Category:
        00      AC_BE        Best Effort
        01      AC_BK        Background
        10      AC_VI        Video
        11      AC_VO        Voice
        
        @rtype:     None
        @return:    None
        """
        
        #The state of MAC must be IDLE, SEND_DATA, or ACK_RECEIVE and no NAV period must be active
        #to make the transmission of an Beacon
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_DATA \
        and self._macState != self._state.WAIT_ACK and self._navEventId:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the Beacon frame now."
            +"The state of MAC is %i." %self._macState)
        
        #Save the state of MAC
        self._saveMacState()
        self._macState = self._state.SEND_BEACON
        
        
        #Decide if a CFP will be present after the Beacon
        if self._hc.applyCFP():
            self._cfp = True
            self._endCfpMax = TIME() + self._bib.beaconInterval * self._TIME_UNIT
        
        
        #Construct Beacon frame
        beacon = self.format.Management()
        
        #FRAME CONTROL FIELD
        fc = self.format.FrameControl()
        #Type and subtype
        fc.type = self._frameType.MANAGEMENT
        fc.subType = self._frameSubType.BEACON
        #toDS and fromDS bits (always set to 0 for management frame)
        fc.toDS = 0
        fc.fromDS = 0
        beacon.frameControl = fc.serialize()
        
        #DURATION ID FIELD
        #When sent during the CFP (always the case with regular Beacon send),
        #the Duration field is set to the value 32 768.
        beacon.durationId = 32768

        #DA FIELD
        beacon.da = "FF:FF:FF:FF:FF:FF" #broacast frame
       
        #SA FIELD
        beacon.sa = self._mib.address
        
        #BSSID FIELD
        beacon.BSSID = self._bib.bssId
                
        #SEQUENCE CONTROL FIELD
        sc = self.format.SequenceControl()
        sc.fragmentNb = 0
        #Increment the sequence number
        self._sequenceNb = (self._sequenceNb +1)%4096 #Count from 0 to 4095
        sc.sequenceNb = self._sequenceNb
        beacon.sequenceControl = sc.serialize()
        
        #DATA FIELD
        beaconData = self.BeaconDataFormat()
        
        #TIMESTAMPS FIELD
        #This field is not use for simulation, the devices is already synchronised by
        #the scheduler (TIME).

        #BEACON INTERVAL FIELD
        beaconData.beaconInterval = self._bib.beaconInterval
        
        #CAPABILITY INFORMATION FIELD
        ci=self.format.CapabilityInfo()
        #BSS Infrastructure (for AP)
        ci.ESS = 1
        ci.iBSS = 0
        #Different Configurations
        #without QoS
        if self._niu.__class__ == AP:
            ci.Qos = 0
            #DCF
            ci.CFPollable = 0
            ci.CFPollableRequest = 0
        #with QoS
        elif self._niu.__class__ == QAP:
            ci.Qos = 1
            #EDCA
            ci.CFPollable = 0
            ci.CFPollableRequest = 0
            if self._mode == "HCCA":
                #CFP or not ?
                if self._cfp:
                    #With a CFP
                    ci.CFPollRequest = 1
                    
            ci.CFPollRequest = 0
           
        else:
            raise ValueError("A STA can not send a broadcast Beacon.")
        
        
        #No confidentiality is used
        ci.privacy = 0
        #ShortPreambule is not use (only for 802.11g) 18.2.2
        ci.shortPreamble = 0
        #Packet binary convolutional code is not use (optional) 18.4.6.6
        ci.PBCC = 0
        #PHY Channel Agility is not use (optional) 18.4.6.7
        ci.channelAgility = 0
        #Spectrum Management is not use
        ci.spectrumManagement = 0
        #Short Slot Time for 802.11g is use (optional) 19.4.4
        ci.shortSlotTime = 1
        #Automatic Power Save Delivery is not use (only for AP)
        ci.APSD = 0
        #DSSS-OFDM is not use (19.7)
        ci.DSSS_OFDM = 0
        #Delayed Block Ack is not use
        ci.delayedBlockAck = 0
        #Immediate Block Ack is not use
        ci.immediateBloackAck = 0
        beaconData.capabilityInformation = ci.serialize()
        
        #SSID and SUPPORTED RATES FIELDS are empty (not use)
        
        #FH, DS, CF and IBSS PARAMETER SET FIELDS are not integrate (optional fields)
        
        #QoS Fields
        if self._niu.__class__ == QAP:
            #QBSS LOAD FIELD id empty (not use)
            #It's only util for a futur roaming implementation and for statistics about load of network
            
            #EDCA PARAMETER SET
            edca = self.format.Element()
        
            #EDCA ELEMENT ID
            edca.elementID = 12
        
            #EDCA LENGTH
            edca.length = 20
        
            #EDCA INFORMATION
            edcaParam = self.format.EDCAParameterSet()
        
            #QOS INFORMATION (for AP)
            QOSInfo = self.format.QosInformationAP()
            #EDCA parameter set update count subfield
            QOSInfo.EDCAParamSetUpdateCount = self._edcaParamUpdateCTR
            #Q-ack bit (not used)
            QOSInfo.Q_Ack = 0
            #Queue request bit
            #AP don't manage a queue of request (if @@@HCCA only)
            QOSInfo.queueRequest = 0
            #TXOP request bit
            #AP accept non 0 TXOP request (if @@@HCCA only)
            QOSInfo.TXOPRequest = 1
            edcaParam.QosInfo = QOSInfo.serialize()
            
            #AC_BE PARAMETER RECORD
            AC_BE_Param = self.format.ACParameterRecord()
            #Arbitrary Inter Frame Sequence Number subfield
            AC_BE_Param.AIFSN = self.AC_BE.EDCATable.AIFSN
            #Admission Control Mandatory subfield
            AC_BE_Param.ACM = 0 #not use the ACI
            #Access Category Index subfield
            AC_BE_Param.ACI = 0
            #Exponential Contention Window minimum
            AC_BE_Param.ECWmin = sqrtint(self.AC_BE.EDCATable.CWmin+1)
            #Exponential Contention Window maximum
            AC_BE_Param.ECWmax = sqrtint(self.AC_BE.EDCATable.CWmax+1)
            #Transmission Opportunity Limit
            AC_BE_Param.TXOPLimit = self.AC_BE.EDCATable.TXOPLimit
            edcaParam.AC_BEParameterRecord = AC_BE_Param.serialize()

            #AC_BK PARAMETER RECORD
            AC_BK_Param = self.format.ACParameterRecord()
            #Arbitrary Inter Frame Sequence Number subfield
            AC_BK_Param.AIFSN = self.AC_BK.EDCATable.AIFSN
            #Admission Control Mandatory subfield
            AC_BK_Param.ACM = 0 #not use the ACI
            #Access Category Index subfield
            AC_BK_Param.ACI = 1
            #Exponential Contention Window minimum
            AC_BK_Param.ECWmin = sqrtint(self.AC_BK.EDCATable.CWmin+1)
            #Exponential Contention Window maximum
            AC_BK_Param.ECWmax = sqrtint(self.AC_BK.EDCATable.CWmax+1)
            #Transmission Opportunity Limit
            AC_BK_Param.TXOPLimit = self.AC_BK.EDCATable.TXOPLimit
            edcaParam.AC_BKParameterRecord = AC_BK_Param.serialize()
            
            #AC_VI PARAMETER RECORD
            AC_VI_Param = self.format.ACParameterRecord()
            #Arbitrary Inter Frame Sequence Number subfield
            AC_VI_Param.AIFSN = self.AC_VI.EDCATable.AIFSN
            #Admission Control Mandatory subfield
            AC_VI_Param.ACM = 0 #not use the ACI
            #Access Category Index subfield
            AC_VI_Param.ACI = 2
            #Exponential Contention Window minimum
            AC_VI_Param.ECWmin = sqrtint(self.AC_VI.EDCATable.CWmin+1)
            #Exponential Contention Window maximum
            AC_VI_Param.ECWmax = sqrtint(self.AC_VI.EDCATable.CWmax+1)
            #Transmission Opportunity Limit
            AC_VI_Param.TXOPLimit = self.AC_VI.EDCATable.TXOPLimit            
            edcaParam.AC_VIParameterRecord = AC_VI_Param.serialize()
            
            #AC_VO PARAMETER RECORD
            AC_VO_Param = self.format.ACParameterRecord()
            #Arbitrary Inter Frame Sequence Number subfield
            AC_VO_Param.AIFSN = self.AC_VO.EDCATable.AIFSN
            #Admission Control Mandatory subfield
            AC_VO_Param.ACM = 0 #not use the ACI
            #Access Category Index subfield
            AC_VO_Param.ACI = 3
            #Exponential Contention Window minimum
            AC_VO_Param.ECWmin = sqrtint(self.AC_VO.EDCATable.CWmin+1)
            #Exponential Contention Window maximum
            AC_VO_Param.ECWmax = sqrtint(self.AC_VO.EDCATable.CWmax+1)
            #Transmission Opportunity Limit
            AC_VO_Param.TXOPLimit = self.AC_VO.EDCATable.TXOPLimit
            edcaParam.AC_VOParameterRecord = AC_VO_Param.serialize()
                
            edca.information = edcaParam.serialize()
        
        beacon.data = beaconData.serialize()
        
        
        #FRAME CHECK SEQUENCE FIELD
        checksum = crc32(beacon.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        beacon.FCS = checksum
       
       
        #Set the next TBTT
        self._targetBeaconTxTime = TIME() + self._bib.beaconInterval * self._TIME_UNIT
       
        
        #Send the beacon frame
        self._sendBuffer = beacon
        self._applyBackoff = False
        self._startProcedureTime = TIME()
        self._channelAccess()
        
        #Called again this same method for the next TBTT to send the following Beacon
        self._beaconEventId = SCHEDULEABS(self._targetBeaconTxTime, self._sendBeacon)


       
    def _sendAck(self):
        """
        Contruct an ACK frame to send it to the entity who has sent the last
        data frame. An ACK is sended only if a valid data frame is received.
        
        @rtype:     None
        @return:    None
        """
        
        #The state of MAC must be IDLE, SEND_DATA or ACK_RECEIVE to make the transmission of an ACK
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_DATA \
        and self._macState != self._state.WAIT_ACK:
            raise ValueError(self._niu._node.hostname  +": Not possible to send the ACK frame now."
            +" The state of MAC is %i." %self._macState)
                  
        #Save the state of MAC if it is not a NAV period
        if not self._navEventId:
            self._saveMacState()
        self._macState = self._state.SEND_ACK

        #Construct ACK frame
        ack = self.format.ACK()

        #FRAME CONTROL FIELD
        fc = self.format.FrameControl()
        fc.type = self._frameType.CONTROL
        fc.subType = self._frameSubType.ACK
        fc.toDS = 0 #toDS and fromDS bits (always set to 0 for control frame)
        fc.fromDS = 0
        ack.frameControl = fc.serialize()

        #DURATION ID FIELD
        ack.durationID = 0 #to set the NAV. Not employed.

        #ADDRESS FIELD
        #The last frame comes from AP (direct or redirection data frame)
        if self._infoFramesCache[0][0] == self._bib.bssId:
            ack.receiverAddress = self._bib.apAddr
        #The last frame comes from STA
        else:
            #Use the Source Address of the last data frame received 
            ack.receiverAddress = self._infoFramesCache[0][0]

        #FRAME CHECK SEQUENCE FIELD
        checksum = crc32(ack.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        ack.FCS = checksum

        self._sendBuffer = ack
        self._applyBackoff = False
        
        #Access to the channel
        self._startProcedureTime = TIME()
        self._channelAccess()
       
                    
                    
    def _retransmission(self):
        """
        Do a retransmission (because of Ack timeout). Three cases are possible:
            - Max autorise retransmission is reached, the transmission has failed.
            - It's the first retransmission. The retry bit must be set and the FCS recalculate
            - In other case, make the retransmission.
            
        Differents statistics update are making during theses cases.
            
        @rtype:     None
        @return:    None
        """
        
        
        if self._navEventId:
            #The retransmission must be reported after the NAV (wake up by NAV Event)
            if self._macState != self._state.SEND_ACK:
                self._macState = self._state.IDLE
            self._retryEventId = None
            return
        
        if (self._macState != self._state.WAIT_ACK):
            if (self._macState != self._state.SEND_ACK) and (self._macState != self._state.SEND_BEACON):
                raise ValueError(self._niu._node.hostname +": Retransmission of data frame is not possible now."
                " State (%i) or last state of MAC is incoherent" %self._macState)
                     
            else:
                if self._macSave['lastMacState'] != self._state.WAIT_ACK:
                    raise ValueError(self._niu._node.hostname +": Retransmission of data frame is not possible now."
                    " State (%i) or last state of MAC is incoherent" %self._macState)
                
                #The Ack Timeout fall in a Beacon or an Ack send
                #The retransmission must be reported after (wake up by mac.sendStatus)
                self._retryEventId = None
                return

        
        if eval("self." +self._backoffEntityTransmit).shortRetryCount >= self._mib.shortRetryLimit:
            #The transmission has failed : the max retransmission autorised is reached
            #Statistics update
            self.stat.framesAborded += 1
            
            #We delete the sended MSDU of the transmission queue
            if self._backoffEntityTransmit == "DCF":
                eval("self." +self._backoffEntityTransmit).transmissionQueue.pop(0)
            else:
                priority, serviceClasse = eval("self." +self._backoffEntityTransmit).transmissionQueue.pop(0)[5:7]
            
            #Inform DL (LLC) and discard the frame
            srcMACAddr = self._mib.address
            #for (Q)AP
            if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
                srcMACAddr = self._sendBuffer.address3
                destMACAddr = self._sendBuffer.address1
            #for (Q)STA
            else:
                srcMACAddr = self._sendBuffer.address2
                destMACAddr = self._sendBuffer.address3

            if self._backoffEntityTransmit == "DCF":
                providedPriority = 0
                providedServiceClass = 0
            else:
                providedPriority = priority
                providedServiceClass = serviceClasse
                
            SCHEDULE(0.0, self._niu.dl.sendStatus, (self._status.UNDELIVERABLE, srcMACAddr,\
            destMACAddr, providedPriority, providedServiceClass))
            
            #Left the MAC sublayer
            self._txInProgress = False
            print "%f : " %TIME() +self._niu._node.hostname +" : TX OFF" #debug
            print " "
            self._retryEventId = None
            self._terminMac()
            
            
        else:
            #Proceed to a new retransmission
            #Update the statistic
            eval("self." +self._backoffEntityTransmit).shortRetryCount += 1
                
            #A Backoff is applied for the next transmission
            self._applyBackoff = True
            
            #Make the retransmission
            self._sendBuffer = None
            self._macState = self._state.IDLE
            self._sendData()
    
    
    
    
    # ---------------------- Receive Methods --------------------------- #
    
    def _receiveData(self, bitstream):
        """
        A Data receive is first always acknolwledge with the send of a ACK 
        to data frame originator. Then STA/AP must deliver the frame content
        to the data link layer. For (Q)AP the redirection of data frame is 
        not made in MAC level but in LLC sublayer.
        
        In this method a test are made to not have an duplicate Frame.
        The essential informations about this last reception is conserved.
        The statistics is updated too.
        
        In a BSS network, if the destination MAC address is not the MAC address 
        of this module, then a redirection is made by the AP.
    
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       PSDU from PHY layer

        @rtype:                 None
        @return:                None
        """
        
        #Parse the bitstream into a MPDU format
        frame = self.MPDUFormat()
        frame.fill(bitstream)
        
        if not self._checkData(frame):
            #We ignore this Data frame
            return
        
        #The state of MAC must be IDLE, SEND_DATA or ACK_RECEIVE to receive a data frame
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_DATA \
        and self._macState != self._state.WAIT_ACK:
            raise ValueError(self._niu._node.hostname  +": Not possible to receive a data frame now."
            +" The state of MAC is %i." %self._macState)
        
        print "%f : " %TIME() +self._niu._node.hostname +" : RX ON" #debug
        print "%f : " %TIME() +self._niu._node.hostname +" : Receive Data" #@@debug
            
        #Send an ACK (unicast frame)
        self._sendAck()
        
            
        if self._duplicateData(frame):
            #The data are not transmit higher
            return
            
            
        #Retrieve informations
        #Address
        #(Q)AP
        if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
            srcMACAddr = frame.address2
            destMACAddr = frame.address3
    
        #(Q)STA
        else:
            srcMACAddr = frame.address3
            destMACAddr = frame.address1
        
        
        #Priority & Service Class
        #With QoS
        if (self._niu.__class__ == QWNIC or self._niu.__class__ == QAP):
            qc = self.format.QosControl()
            qc.fill(frame.qosControl)
            priority = qc.tid
            serviceClass = qc.ackPolicy
            
            if self._niu.__class__ == QAP and qc.eosp == 1:
                #Obtain the information about the size of transmission queue
                if not self._hc.queueSize.has_key(srcMACAddr):
                    #NEW QSTA
                    #Create the dictionnary with MAC address for the keys
                    for key in self._bib.staAddr:
                        self._hc.queueSize[key] = [0, 0, 0, 0] #Create a list for the 4 ACs
                          
                if priority == 0: #AC_BE
                    index=0
                elif priority == 1 or priority == 2: #AC_BK
                    index=1
                elif priority == 3 or priority == 4 or priority == 5: #AC_VI
                    index=2
                elif priority == 6 or priority == 7: #AC_VO
                    index=3
                    
                self._hc.queueSize[srcMACAddr][index]= qc.txopOrQueue

      
        #Without QoS
        else:
            priority  = 0 #DCF
            serviceClass = 0 #Normal acknowledgement
        
        
        
        #If the destination MAC address is not the MAC address of this module, then a redirection
        #must be made by the AP (Infrastructure network). The information doesn't up higher.
        if destMACAddr != self._mib.address:
            #Place the redirected data frame in the queue of transmission
            #With QoS
            if (self._niu.__class__ == QAP):
                            
                #Determine Access Category
                if priority == 0:
                    accessCategory = "AC_BE"
                    index=0
                
                elif priority == 1 or priority == 2:
                    accessCategory = "AC_BK"
                    index=1
                    
                elif priority == 3 or priority == 4 or priority == 5:
                    accessCategory = "AC_VI"
                    index=2
                    
                elif priority == 6 or priority == 7:
                    accessCategory = "AC_VO"
                    index=3
                 
                #Update QAP queues informations for the HC                 
                self._hc.queueSize[self._bib.apAddr][index] = len(eval("self." +accessCategory).transmissionQueue)
                
                #Increment the MSDU ID
                self._msduId = (self._msduId +1)%256 #ID from 0 to 255
    
                #Life time event
                #When the life time is time up (MSDU will be discarded).
                lifeTimeEvent = SCHEDULE(eval("self." +accessCategory).EDCATable.MSDULifeTime\
                * self._TIME_UNIT, self._discardMsdu, (self._msduId, accessCategory))
                    
                #Add an list of information in last place in Transmission Queue
                eval("self." +accessCategory).transmissionQueue.append([self._msduId, frame.data, frame.address3, \
                frame.address1, frame.address2, priority, serviceClass, lifeTimeEvent])

                                      
                                         
            #Without QoS
            elif (self._niu.__class__ == AP):
                #Add an tuple of information in last place in Transmission Queue
                self.DCF.transmissionQueue.append(frame.data, frame.address3, frame.address1, frame.address2)


            else:
                raise ValueError(self._niu._node.hostname  +": Not possible to redirect a data frame for a (Q)STA.")
            
            
            #Wait the next liberation of MAC layer to send the redirected data frame
            return
            
            
            
        else:
            #Deliver the frame content to the data link layer
            self._niu.dl.receive(frame.data, srcMACAddr, destMACAddr, priority, serviceClass)
            
    
    
    
    def _receiveAck(self, bitstream):
        """
        Reception of an ACK frame:
          - Check frame
          - Update statistics about send
          - Inform LLC (dl.sendStatus)
          - EDCA TXOP Management (+ control TBTT)
          - Clean up the actual transmission
        
        
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       PSDU from PHY layer

        @rtype:                 None
        @return:                None
        """
        
        #Test the length of bitstream
        if len(bitstream) != self._ACKSIZE:
            raise ValueError(self._niu._node.hostname  +": The bitstream received has not the good size for an ACK frame: " 
            +len(bitstream))
            
        #Parse the bitstream into an ACK format
        ack = self.format.ACK()
        ack.fill(bitstream)
        
        if not self._checkAck(ack):
            #We ignore this ACK frame
            return
            
            
        #The state of MAC must be ACK_RECEIVE to receive an ack frame
        if self._macState != self._state.WAIT_ACK:
            raise ValueError(self._niu._node.hostname  +": Not possible to receive a ACK frame now."
            +"The state of MAC is %i." %self._macState)
             
        self._txInProgress = False
        print "%f : " %TIME() +self._niu._node.hostname +" : Receive Ack" #debug
        print "%f : " %TIME() +self._niu._node.hostname +" : TX OFF" #debug
        print " "
        
        #We cancel the retransmission event
        if self._retryEventId:
            CANCEL(self._retryEventId)
            self._retryEventId = None
            
        #We delete the sended MSDU of the transmission queue
        if self._backoffEntityTransmit == "DCF":
            eval("self." +self._backoffEntityTransmit).transmissionQueue.pop(0)
        else:
            priority, serviceClasse = eval("self." +self._backoffEntityTransmit).transmissionQueue.pop(0)[5:7]
            
        #Statistics update about send (correspond to the last send data frame)
        self.stat.framesTransmittedOK += 1
        self.stat.octetsTransmittedOK += len(self._sendBuffer.data)

        #Inform LLC of the transmission success
        srcMACAddr = self._mib.address
        #for (Q)AP
        if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
            destMACAddr = self._sendBuffer.address1
        #for (Q)STA
        else:
            destMACAddr = self._sendBuffer.address3
         

        if self._backoffEntityTransmit == "DCF":
            providedPriority = 0
            providedServiceClass = 0
        else:
            providedPriority = priority
            providedServiceClass = serviceClasse
        
        
        SCHEDULE(0.0, self._niu.dl.sendStatus, (self._status.SUCCESS, srcMACAddr, destMACAddr,
        providedPriority, providedServiceClass))
                
               
        #EDCA TXOP Management
        #Test if EDCA TXOP is longer than one transmission procedure
        if eval("self." +self._backoffEntityTransmit).EDCATable.TXOPLimit != 0:
            #Test if there are still frames in the transmission queue
            if len(eval("self." +self._backoffEntityTransmit).transmissionQueue) > 0:
                
                #Compute the remain TXOP
                #If we are in a EDCA TXOP period
                if self._txop or self._cap:
                    self._remainTXOP = self._remainTXOP - (TIME() - self._latestStartTransmitActivity)
            
                #If it was the first frame of EDCA TXOP
                else:
                    #The current AC has obtained the EDCA TXOP (first frame)
                    self._txop = True
                    #Retrieve the first remain TXOP
                    self._remainTXOP = eval("self." +self._backoffEntityTransmit).EDCATable.TXOPLimit * 1e-6 \
                    - (TIME() - self._latestStartTransmitActivity)
        
                #The TXOP must be terminated SIFS before the TBTT
                timeRemainToTBTT = self._targetBeaconTxTime - TIME()
                if self._remainTXOP > timeRemainToTBTT - self._niu.phy.computeIFS()[0]:
                    self._remainTXOP = timeRemainToTBTT - self._niu.phy.computeIFS()[0] - self._MIN_UNIT
        
                #Compute next total transmission time (DATA+ACK+2*SIFS)
                nextTxDuration = self._niu.phy.getTransmissionTime(len(eval("self." +self._backoffEntityTransmit).transmissionQueue[0][1])+self._DATAHEADER) \
                + self._niu.phy.getTransmissionTime(self._ACKSIZE) + 2*self._niu.phy.computeIFS()[0]

                
                if  nextTxDuration < self._remainTXOP:
                    if self._txop:
                        print "%f : " %TIME() +self._niu._node.hostname +" : EDCA TXOP : remainTXOP = %f" %self._remainTXOP +" nextTxDuration = %f" %nextTxDuration #debug
                        lifeTimeEvent = eval("self." +self._backoffEntityTransmit).transmissionQueue[0][7]
                        print "%f : " %TIME() +self._niu._node.hostname +" : Select " +self._backoffEntityTransmit +" MSDU %i (EDCA TXOP) to send" %lifeTimeEvent[3] [0] #debug
                    elif self._cap:
                        print "%f : " %TIME() +self._niu._node.hostname +" : CAP : remainCAP = %f" %self._remainTXOP +" nextTxDuration = %f" %nextTxDuration #debug
                        lifeTimeEvent = eval("self." +self._backoffEntityTransmit).transmissionQueue[0][7]
                        print "%f : " %TIME() +self._niu._node.hostname +" : Select " +self._backoffEntityTransmit +" MSDU %i (CAP) to send" %lifeTimeEvent[3] [0] #debug
                        
                    
                    #Save the actual transmit Backoff Entity and cloture the transmission
                    ActualBackoffEntity = self._backoffEntityTransmit
                    self._terminMac()
                    
                    #Send the next MSDU of the transmision queue of the current AC
                    self._backoffEntityTransmit = ActualBackoffEntity
                    self._txInProgress = True
                    print "%f : " %TIME() +self._niu._node.hostname +" : TX ON (receiveAck)" #debug
                    self._sendData()
                    return
                else:
                    print "%f : " %TIME() +self._niu._node.hostname +" : End of EDCA TXOP"
                    
        
        #The TXOP/CAP is finished (or no TXOP was applied)
        self._txop = False
        self._cap = False
        #Reapply the NAV in a CFP
        if self._cfp:
            self._setNAV(0)
        
        #Initialize the privates variables for a futur transmission
        self._terminMac()
          

    
    
    def _receiveQosCfPoll(self, bitstream):
        """
        Reception of an QoS CF-Poll frame by a (Q)STA.
    
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       PSDU from PHY layer

        @rtype:                 None
        @return:                None
        """   
        
        #Must be a QSTA to receive a QoS CF-Poll frame
        if not self._niu.__class__ == QWNIC:                
            return
            

        #The state of MAC must be IDLE, SEND_DATA or WAIT_ACK to receive an QoS CF-Poll frame
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_DATA \
        and self._macState != self._state.WAIT_ACK:
            raise ValueError(self._niu._node.hostname  +": Not possible to receive a QoS CF-Poll frame now."
            +"The state of MAC is %i." %self._macState)
    
    
        #Parse the bitstream into an Data frame format
        cfPoll = self.format.MPDUQos()
        cfPoll.fill(bitstream)
        

        if not self._checkData(cfPoll):                
            #We ignore this QoS CF-Poll frame
            return
    
        print "%f : " %TIME() +self._niu._node.hostname +" : Receive QoS CF-Poll" #@@debug
        
        #We ignore the QoS CF-Poll if the state of MAC is WAIT_ACK
        if self._macState == self._state.WAIT_ACK:
            return
            
        #the NAV is stopped if we are in a Contention Free Period
        if self._cfp:
            self._endNAV()
            
    

        #If data is present in transmissions queues
        if self.AC_BE.transmissionQueue or self.AC_BK.transmissionQueue \
        or self.AC_VI.transmissionQueue or self.AC_VO.transmissionQueue:
        
            #QoS Control field
            qc = self.format.QosControl()
            qc.fill(cfPoll.qosControl)
            priority = qc.tid
            serviceClass = qc.ackPolicy
            
            if qc.txopOrQueue:
                #New CAP
                self._cap = True
                #Remain TXOP
                self._remainTXOP = qc.txopOrQueue * 32e-6
                
                #The TXOP must be terminated SIFS before the TBTT
                timeRemainToTBTT = self._targetBeaconTxTime - TIME()
                if self._remainTXOP > timeRemainToTBTT - self._niu.phy.computeIFS()[0]:
                    self._remainTXOP = timeRemainToTBTT - self._niu.phy.computeIFS()[0] - self._MIN_UNIT
            

            if self._macState == self._state.IDLE:
                self._selectNextMSDU()
            else:
                #The MSDU is already constructed but not yet sended
                if not self._navEventId:
                    #Compute next total transmission time (DATA+ACK+2*SIFS)
                    nextTxDuration = self._niu.phy.getTransmissionTime(len(self._sendBuffer.serialize()))
                    + self._niu.phy.getTransmissionTime(self._ACKSIZE) + 2*self._niu.phy.computeIFS()[0]
                
                
                    if  nextTxDuration < self._remainTXOP:
                        if  len(eval("self." +self._backoffEntityTransmit).transmissionQueue) > 1:
                            print "%f : " %TIME() +self._niu._node.hostname +" : CAP : remainCAP = %f" %self._remainTXOP +\
                            " nextTxDuration = %f" %nextTxDuration #debug
                        self._applyBackoff = False
                        self._startProcedureTime = TIME()
                        self._channelAccess()
                    else:
                        return
                        
                else:
                    print ERROR #@@@To do
        
            
        #If no data is present in transmissions queues
        else:
            return
    
    
    
    def _receiveCfEnd(self, bitstream):
        """
        Reception of an CF-End frame by a QSTA to end the Contention
        Free Period.
    
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       PSDU from PHY layer

        @rtype:                 None
        @return:                None
        """   
        
        #Must be a QSTA to receive a QoS CF-End frame
        if not self._niu.__class__ == QWNIC:                
            return
    
        #The state of MAC must be IDLE to receive an QoS CF-Poll frame
        if self._macState != self._state.IDLE:
            raise ValueError(self._niu._node.hostname  +": Not possible to receive a CF-End frame now."
            +"The state of MAC is %i." %self._macState)
    
        print "%f : " %TIME() +self._niu._node.hostname +" : Receive CF-End" #@@debug
    
        #Parse the bitstream into an CF-End format
        cfEnd = self.format.CF-END()
        cfEnd.fill(bitstream)

        if not self._checkCfEnd(cfEnd):                
            #We ignore this CF-End frame
            return
    
        #The CFP is finished, thus the NAV too.
        self._cfp = False
        self._endNAV()
        
        #Left the MAC sublayer
        self._terminMac()
    
    
    
    def _receiveBeacon(self, bitstream):
        """
        Reception of an Beacon frame by a (Q)STA.
    
    
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       PSDU from PHY layer

        @rtype:                 None
        @return:                None
        """

        
        #There is a Beacon Management in the BSS
        #If it's the first beacon received, set the next TBTT even if the frame is not valid
        if not self._beacon:
            #It's the first beacon received
            self._beacon = True
            #Set the next TBTT value even if there is an error in Beacon
            self._newTBTT()
        
        
        #Parse the bitstream into an Beacon format
        beacon = self.format.Management()
        beacon.fill(bitstream)

        if not self._checkBeacon(beacon):                
            #We ignore this Beacon frame
            return

        #The state of MAC must be IDLE, SEND_DATA or ACK_RECEIVE and NAV must be not active 
        #to receive a Beacon frame
        if self._macState != self._state.IDLE and self._macState != self._state.SEND_DATA \
        and self._macState != self._state.WAIT_ACK and self._navEventId:
            raise ValueError(self._niu._node.hostname  +": Not possible to receive a Beacon frame now."
            +"The state of MAC is %i." %self._macState)
            
        print "%f : " %TIME() +self._niu._node.hostname +" : Receive Beacon" #@@debug

        #Data field
        data = self.BeaconDataFormat()
        data.fill(beacon.data)

        #Update the Beacon Interval
        if self._bib.beaconInterval != data.beaconInterval:
            self._bib.beaconInterval = data.beaconInterval
            #Set the next new TBTT
            self._newTBTT()

       
        #Capability Info field
        ci = self.format.CapabilityInfo()
        ci.fill(data.capabilityInfo)

        
        #Read the Qos fields if the entity have the QoS capacity
        if ci.Qos and (self._niu.__class__ == QWNIC):
        
            #EDCA Parameter Set
            edcaElement = self._Element
            edcaElement.fill(data.EDCAParamSet)
            edcaParam = self._EDCAParameterSet
            edcaParam.fill(edcaElement.information)
            qosInfo = self._QOSInfo()
            qosInfo.fill(edcaParam.QOS)
            
            #Control if the EDCA must be updated
            if qosInfo.EDCAParamSetUpdate != self._edcaParamUpdateCTR:
                #Update the EDCA parameter
                acParam = _ACParameterRecord()
                #AC_BE
                acParam.fill(edcaParam.AC_BEParameterRecord)
                self.AC_BE.EDCATable.AIFSN = acParam.AIFSN
                self.AC_BE.EDCATable.CWmin = 2**acParam.ECWmin-1
                self.AC_BE.EDCATable.CWmax = 2**acParam.ECWmax-1
                self.AC_BE.EDCATable.TXOPLimit = acParam.TXOPLimit
                #AC_BK
                acParam.fill(edcaParam.AC_BKParameterRecord)
                self.AC_BK.EDCATable.AIFSN = acParam.AIFSN
                self.AC_BK.EDCATable.CWmin = 2**acParam.ECWmin-1
                self.AC_BK.EDCATable.CWmax = 2**acParam.ECWmax-1
                self.AC_BK.EDCATable.TXOPLimit = acParam.TXOPLimit
                #AC_VI
                acParam.fill(edcaParam.VI_BKParameterRecord)
                self.AC_VI.EDCATable.AIFSN = acParam.AIFSN
                self.AC_VI.EDCATable.CWmin = 2**acParam.ECWmin-1
                self.AC_VI.EDCATable.CWmax = 2**acParam.ECWmax-1
                self.AC_VI.EDCATable.TXOPLimit = acParam.TXOPLimit
                #AC_VO
                acParam.fill(edcaParam.AC_VOParameterRecord)
                self.AC_VO.EDCATable.AIFSN = acParam.AIFSN
                self.AC_VO.EDCATable.CWmin = 2**acParam.ECWmin-1
                self.AC_VO.EDCATable.CWmax = 2**acParam.ECWmax-1
                self.AC_VO.EDCATable.TXOPLimit = acParam.TXOPLimit                
                
        
            #Test if a CFP is present
            if ci.CFPollRequest:
                self._cfp = True
                #Apply a non-finite NAV
                self._setNAV(0)
        
    
    
    # --------------------- Control Methods ---------------------------- #
    
    def _checkData(self, frame):
        """
        Valid the data frame if the following checks are successful:
            - Destination Address field
            - FCS
            
        Manage the EIFS functionalities. If error, make update about statistics too.
        
        This method conserve the following informations of the last frame 
        received in a tuple:
            - Source address
            - Sequence number
            - Fragment number
        
        A cache is used to contened a max of 10 tuples.
        The indice 0 of cache is always the actual received frame 
        (use for ACk send).
        
        
        @type frame:    Instance of a frame constructor class
        @param frame:   MAC Data frame to be checked
            
        @rtype:         Boolean
        @return:        TRUE if the Data frame is OK, FALSE otherwise
        """
        _cacheSize = 10
        
        #Check if the frame shall be accepted (Destination Address)
        destAddr = frame.address1
        addrNoMatch = False
        
        #for (Q)AP
        if (self._niu.__class__ == AP or self._niu.__class__ == QAP):
            if (destAddr != self._bib.bssId):
                #The frame is not destinated for this (Q)AP or there is error in address field
                addrNoMatch = True
           
        #for (Q)STA
        elif (destAddr != self._mib.address):
            #The frame is not destinated for this (Q)STA or there is error in address field
            addrNoMatch = True

            
        #Control FCS
        if not self._controlFCS(frame):
            #FCS not passed ==> Frame Error
            if not addrNoMatch:
                #Statistics update
                if frame.data:
                    self.stat.framesReceivedFCSErrors += 1
                    self.stat.octetsReceivedError += len(frame.data)
                    
                else:
                    #QoS CF-Poll frame
                    self.stat.cfPollReceivedFCSErrors += 1
                    
                #EIFS shall be used in the place of DIFS
                self._lastFrameError = True
            
            return False

        else:

            #Test if a NAV must be applied because a TXOP is present (multi-frame transmission)
            if frame.durationID:
                self._setNAV(frame.durationID*1e-6)
        
            #If there is no the good address, but the FCS is OK
            if addrNoMatch:
                #No statistics update
                return False

        #If we are in a EIFS period, the EIFS is stopped for next transmit frame
        self._lastFrameError = False
        
        #Conserve Source address, Sequence number and Fragment number in the cache
        sc = self.format.SequenceControl()
        sc.fill(frame.sequenceControl)
        if len(self._infoFramesCache) > _cacheSize: #fixe a maximum size of cache
            self._infoFramesCache.pop() #Clear last item of cache
        #Add an tuple of information in first place in cache
        self._infoFramesCache.insert(0, (frame.address2, sc.sequenceNb, sc.fragmentNb))
        return True
        
   
   
    def _duplicateData(self, frame):
        """        
        A test is make to know if the last data frame received is 
        a duplicate frame or not.
        
        Make the statistics update for duplicate received data and
        for data frame received OK.

        
        @type frame:    Instance of a frame constructor class
        @param frame:   MAC Data frame received
            
        @rtype:         Boolean
        @return:        TRUE if the Data is a duplicate frame, FALSE otherwise
        """
        
        #Control if this data is a duplicate frame
        #only if the retry bit is active.
        fc = self.format.FrameControl()
        fc.fill(frame.frameControl)
        
        if fc.retry:
            sc = self.format.SequenceControl()
            sc.fill(frame.sequenceControl)
            #Control if the number of sequence and address source are the same
            #of one of last frame.
            
            for infoFrame in self._infoFramesCache[1:]:
                if sc.sequenceNb == infoFrame[1] \
                and frame.address2 == infoFrame[0]:
                    #The frame is the same of one of the last, it's a duplicate frame
                    #Statistics update
                    self.stat.duplicateFramesReceived += 1
                    self.stat.octetsReceivedError += len(frame.data)
                    print "%f : " %TIME() +self._niu._node.hostname +" : The frame received is a duplicate Data" #@@debug
                    return True
        
        
        #Statistics update (data received is OK)
        if frame.data:
            self.stat.framesReceivedOK += 1
            self.stat.octetsReceivedOK += len(frame.data)
        else:
            #QoS CF-Poll frame
            self.cfPollReceivedOK
        
        return False


              
    def _checkAck(self, ack):
        """
        Valid the ACK frame if the following checks are successful:
            - Receiver Address field
            - FCS
            
        Update the satistics about this ACK frame received.
        
        @type ack:    Instance of a frame constructor class
        @param ack:   MAC ACK frame to be checked
            
        @rtype:         Boolean
        @return:        TRUE if the ACK frame is OK, FALSE otherwise
        """
        
        #Check if the frame shall be accepted (Receiver Address)
        if (ack.receiverAddress != self._mib.address):
            #This frame is not destinated for this device or there is error in address field
            #Not possible to know. No Statistics update.
            return False
        
        #Check the FCS
        if not self._controlFCS(ack):
            #Statistics update
            self.stat.ackReceivedFCSErrors += 1
            return False
        
        
        #Statistics update
        self.stat.ackReceivedOK += 1
        return True
    


    def _checkCfEnd(self, cfEnd):
        """
        Valid the CF-Enf frame if the following checks are successful:
            - Receiver Address field
            - FCS
            
        Update the satistics about this CF-End frame received.
        
        @type cfEnd:    Instance of a frame constructor class
        @param cfEnd:   CF-End frame to be checked
            
        @rtype:         Boolean
        @return:        TRUE if the ACK frame is OK, FALSE otherwise
        """
        
        #Check if the frame shall be accepted (Receiver Address)
        if (cfEnd.receiverAddress != self._mib.address):
            #This frame is not destinated for this device or there is error in address field
            #Not possible to know. No Statistics update.
            return False
        
        #Check the FCS
        if not self._controlFCS(cfEnd):
            #Statistics update
            self.stat.cfEndReceivedFCSErrors += 1
            return False
        
        #Statistics update
        self.stat.cfEndReceivedOK += 1
        return True    
        
        
        
    def _checkBeacon(self, beacon):
        """
        Valid the beacon frame if the following checks are successful:
            - Receiver Address field (broadcast or unicast)
            - FCS
            
        Update the satistics about this Beacon frame received.
        
        @type beacon:    Instance of a frame constructor class
        @param beacon:   MAC ACK frame to be checked
            
        @rtype:         Boolean
        @return:        TRUE if the Beacon frame is OK, FALSE otherwise
        """

        #Check if the frame shall be accepted (Receiver Address)
        if beacon.DA != self._mib.address and beacon.DA != "FF:FF:FF:FF:FF:FF":
            #This frame is not destinated for this device or there is error in address field
            #Not possible to know. No Statistics update.
            return False

        #Check the FCS
        if not self._controlFCS(beacon):
            #Statistics update
            self.stat.beaconReceivedFCSErrors += 1
            return False 
  
        
        #Statistics update
        self.stat.beaconReceivedOK += 1
        return True
        
        
        
    def _controlFCS(self, frame):
        """
        Determine if a 802.11 MAC frame is corrupted or not with the Frame Check Sequence.
        
        @type frame:    Instance of a frame constructor class
        @param frame:   MAC frame to be controlled with the FCS
        
        @rtype:         Boolean
        @return:        TRUE if the FCS dected no error, FALSE if the frame has errors
        """
        
        #Control the FCS
        checksum = crc32(frame.serialize()[0:-4]) & ((1L<<32)-1) #Take lower 32 bit
        return (frame.FCS == checksum)
            
    
      
    # --------------------- CSMA-CA Methods ---------------------------- #
    
    def _backoff(self):
        """
        Decide if Backoff must be applied. If yes, wait the random or remain Backoff.
        
        @rtype:     Boolean
        @return:    True if Backoff must be applied.
        """
        
        #It must be no Backoff procedure in progress
        if not self._backoffEventId:
       
            #Execute Backoff only when we must apply
            if self._applyBackoff:
    
                if (eval("self." +self._backoffEntityTransmit).remainBackoffCTR == 0):
                    #With a new Backoff
                    backoff = self._computeBackoff(self._backoffEntityTransmit) * self._niu.phy.getSlotTime()
    
                else:
                    #With the remain Backoff
                    backoff = eval("self." +self._backoffEntityTransmit).remainBackoffCTR* self._niu.phy.getSlotTime()
                    
    
                #Report the transmission if the next TBTT is encroached by the backoff (called by channelIdle())
                if self._beacon:
                    if TIME() + backoff > self._targetBeaconTxTime:
                        if self._txop or self._cap:
                            raise ValueError(self._niu._node.hostname +": Want to access to the channel in a TXOP/CAP"
                            +" but TBTT will be encroached (Test must be made in method ReceiveACK)")
                        else:    
                            #Use the remain Backoff
                            eval("self." +self._backoffEntityTransmit).remainBackoffCTR = int(self._targetBeaconTxTime - TIME()\
                            - self._niu.phy.computeIFS()[0]/self._niu.phy.getSlotTime() + 1) # round up
                                
                            #The transmission is reported after the reception of beacon
                            #will be recalled by mac.channelIdle()
                            print "%f : " %TIME() +self._niu._node.hostname +" : The transmission is reported after the reception of beacon. TBTT: %f (Backoff)"\
                            %self._targetBeaconTxTime #@@debug
                            self._applyBackoff = True
                            
                        return True
                        
                #The Backoff can be applied
                print "%f : " %TIME() +self._niu._node.hostname +" : Backoff Value: " +str(backoff)#debug
                self._backoffEventId = SCHEDULE(backoff, self._endBackoff)
                return True
            
            #Pass the Backoff (no need to apply or already applied)
            elif self._backoffEventId:
                return False
                
        else:
            #There is already a Backoff Procedure, wait its end            
            return True
    
    
    
    def _computeBackoff(self, entity):
        """
        Compute the random Backing Off in number of Slot Time for the current Backoff entity. 
        The CW increase exponential with the number of retransmission i. (section 9.2.4)
        (CWi = 2**i (CWmin + 1)-1).
        
        @type entity:    String
        @param entity:   For which entity the backoff is computed (AC_BK, AC_BE, AC_VI, AC_VO, DCF)
        
        @rtype:     Integer
        @return:    Random backing Off in Slot Time
        """

        CW = min(eval("self." +entity).EDCATable.CWmax, 2**eval("self." +entity).shortRetryCount \
        *(eval("self." +entity).EDCATable.CWmin + 1) - 1)
        backoff = randint(0,CW)
        return backoff

        


    def _endBackoff(self):
        """
        Cloture a Backoff procedure. Called at the end of a backoff by event 
        or when a data frame is received.
        
        There are 2 cases where the remain Backoff will be retrieve:
            - The Backoff is end but the channel is busy
            - A data frame is arrived before the end of Backoff (channel busy)
        
        @rtype:     None
        @return:    None
        """

        #The state of MAC must be SEND_DATA to cloture a Backoff procedure
        if self._macState != self._state.SEND_DATA:
            raise ValueError(self._niu._node.hostname  +": Not possible to cloture the Backoff now."
            +" The state of MAC is %i." %self._macState)
            
                
        #Test if the stop time of event is higher of the actual time
        if self._backoffEventId[0] > TIME():
            #The Backoff was canceled because a data frame is arrived before the end of Backoff.
            #Retrieve the Remain Backing Off.
            eval("self." +self._backoffEntityTransmit).remainBackoffCTR = int((self._backoffEventId[0] - \
            self._niu.phy.getTimeLastReceiveActivity()) / self._niu.phy.getSlotTime() + 1) #Round up
                
            #The Backoff period is left
            self._backoffEventId = None
            
            #Try again to send the frame when the channel will be free
            self._applyBackoff = True
            return
        
        
        #The event was raised normally
        elif self._niu.phy.carrierSense():
            #The channel is Busy
            #Retrieve the Remain Backing Off for the next Backoff of this reported transmission.
            eval("self." +self._backoffEntityTransmit).remainBackoffCTR = int((TIME() - \
            self._niu.phy.getTimeLastReceiveActivity()) / self._niu.phy.getSlotTime() + 1)  # round up
                
            if (eval("self." +self._backoffEntityTransmit).remainBackoffCTR > self._niu.phy.getCW('max')):
                raise ValueError(self._niu._node.hostname +": The compute remain Backoff is not possible.")

            #The Backoff period is left
            self._backoffEventId = None

            #Try again to send the frame when the channel will be free
            self._applyBackoff = True
            return

        else:
            #The channel is Idle and no data frame was received. The frame will be send.
            eval("self." +self._backoffEntityTransmit).remainBackoffCTR = 0
                
            #The Backoff period is left
            self._backoffEventId = None
                
            self._applyBackoff = False
            self._channelAccess()
    
    
    # --------------------- Beacon Management Methods ---------------------------- #    
    
    
    def _startBeacon(self):
        """
        Begin a new Beacon Management if the mode is not DCF. The first Beacon 
        is sended immediately. After the Beacons is send all the Beacon interval
        (definite in self._bib).
    
        @rtype:     None
        @return:    None
        """
        
        if self._mode == "DCF":
            return
        
        self._beacon = True
        
        #Start Beacon management
        self._beaconEventId = SCHEDULE(0.0, self._sendBeacon)
    
    
    
    
    def _stopBeacon(self):
        """
        Stop the Beacon Management.
        
        @rtype:     None
        @return:    None
        """
    
        self._beacon = False
        
        #Stop Beacon management
        CANCEL(self._beaconEventId)
        self._beaconEventId = None
    
    



    # --------------------- Transmissions queues Management ---------------------------- #       
    
    
    def _discardMsdu(self, id, ac):
        """ 
        Discard MSDU id of the transmissions queues without condition. The reason
        is the end of the lifetime of the MSDU.
        
        @type id:   Integer
        @param id:  ID of the MSDU to discard
        
        @type ac:   Integer
        @param ac:  Access Category who is the MSDU to discard

        @rtype:     None
        @return:    None
        """
    
        #Search ID in the Buffer
        index=0
        for msdu in eval("self."+ac).transmissionQueue:
            if msdu[0] == id:
                #Set 2 EDCA parameters if the MSDU is the first in transmission queue
                if msdu == eval("self."+ac).transmissionQueue[0]:
                    eval("self."+ac).remainBackoffCTR = 0
                    eval("self."+ac).shortRetryCount = 0
           
                #If the MSDU to discarded is the actual MSDU in transmission
                #it is not discarded now
                if self._macState == self._state.SEND_DATA and index == 0:
                    #New Life time event
                    lifeTimeEvent = SCHEDULE(eval("self." +ac).EDCATable.MSDULifeTime\
                    * self._TIME_UNIT, self._discardMsdu, (id, ac))
                    #Update the Life Time Event
                    eval("self." +ac).transmissionQueue[0][7] = lifeTimeEvent
                    return
            
                #If we are in TXOP period and the MSDU is the second of the 
                #transmission queue, it is not discarded now. (Avoid a probleme with NAV 
                #of the destination STA)
                if self._txop or self._cap and index == 1:
                    #New Life time event
                    lifeTimeEvent = SCHEDULE(eval("self." +ac).EDCATable.MSDULifeTime\
                    * self._TIME_UNIT, self._discardMsdu, (id, ac))
                    #Update the Life Time Event
                    eval("self." +ac).transmissionQueue[1][7] = lifeTimeEvent
                    return
                   
                
                #Discard MSDU
                print "%f : " %TIME() +self._niu._node.hostname +" : " +ac +" MSDU %i is discarted." %id #debug
                eval("self." +ac).transmissionQueue.pop(index)
                self.stat.msduDeleted += 1
                return
            index += 1
    
        assert(self._niu._node.hostname +"The MSDU ID (%i)"%id +"has not found in the " +ac +" transmission queue.")
    

    
    
    
    
class LLC(DLTop):
    """ 
    The LLC sublayer is used as adaptation for the Network Layer.
    just pass data received from upper layer to MAC sublayer.
    """
    
        
    def __init__(self):
        self._upperLayers = []
        """List to contain the upper layer protocol entity."""
        self._waitingForIdleMac = False
        """True, if while a transmission is deferred due to the MAC occupation."""



    def install(self, niu, protocolName):
        """
        This method is called by the one of following NIU (device) to inform
        the protocol that is has been installed :
            - WNIC
            - QWNIC
            - AP
            - QAP

        The method initialize the LLC protocol with the registered of the NIU
        for later access.

        @type niu:              NIU
        @param niu:             NIU on which self is installed. Must be WNIC, QWNIC, AP or QAP.

        @type protocolName:     String
        @param protocolName:   Name of protocol. Must be 'dl'.

        @rtype:                 None
        @return:                None
        """
    
    
        if isinstance(niu, NIU):
            if (niu.__class__ == NIC):
                raise TypeError("802.11 LLC sublayer could not be installed on a NIC")
            self._niu = niu
        else:
            raise TypeError("802.11 LLC sublayer must be installed on a NIU (AP, QAP, WNIC or QWNIC)")
            
        if protocolName != "dl":
            raise NameError("802.11 LLC sublayer must be installed under "
                            "the name 'dl'")
        self._protocolName = "dl"
        self.fullName = niu.fullName + ".dl"
        


    def registerUpperLayer(self, upperProtocolEntity):
        """
        Register an upper layer protocol to receive packet.

        @type upperProtocolEntity:  ProtocolEntity
        @param upperProtocolEntity: Receiver of packets.

        @rtype:                 None
        @return:                None
        """
        
        #Add a upper layer protocol in self._upperLayers (list)
        self._upperLayers.append(upperProtocolEntity)



    def send(self, bitstream, srcMACAddr, destMACAddr, priority, serviceClass):
        """
        Accept a bitstream from the NW layer and try to send it.

        If it cannot be sent, put it into a transmission buffer and wait
        until MAC becomes available for the next packet (call of dl.sendStatus).
        
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       Data to send
        
        @type srcMACAddr:       MAC Address (String)
        @param srcMACAddr:      MAC Address source
        
        @type destMACAddr:      MAC Address (String)
        @param destMACAddr:     MAC Address destination

        @type priority:         Integer
        @param priority:        Priority of Data (TID: 0-15). 0 = DCF.

        @type serviceClass:     Boolean
        @param serviceClass:    Service Class of Data (True = QoSAck, False = QoSNoAck)
        
        @rtype:                 None
        @return:                None
        """
        
        #Initiate a transmission
        self._niu.mac.send(bitstream, srcMACAddr, destMACAddr, priority, serviceClass)



    def receive(self, bitstream, srcMACAddr, destMACAddr, priority, serviceClass):
        """
        Accept a pdu from the DLBottom. Transfer to the upper layer protocols.
        Don't transfer if it's a redirection by the AP.
        
        @type bitstream:        Bitstream (list of char)
        @param bitstream:       Data to receive

        @type srcMACAddr:       MAC Address (String)
        @param srcMACAddr:      MAC Address source

        @type destMACAddr:      MAC Address (String)
        @param destMACAddr:     MAC Address destination

        @type priority:         Integer
        @param priority:        Priority of Data (TID: 0-15). 0 = DCF.

        @type serviceClass:     Boolean
        @param serviceClass:    Service Class of Data (True = QoSAck, False = QoSNoAck)

        @rtype:                 None
        @return:                None
        """
        
        self._upperLayers[0].receive(bitstream, srcMACAddr, destMACAddr, priority, serviceClass)
        



    def sendStatus(self, txStatus, srcMACAddr, destMACAddr, providedPriority, providedServiceClass):
        """
        Called by DLBottom (MAC) at the end of a data transmission.

        @type txStatus:                 MAC Status (Integer)
        @param txStatus:                Status of the last send data frame: SUCCESS, UNDELIVERABLE, UNAVAILABLE_PRIORITY

        @type srcMACAddr:               MAC address (String)
        @param srcMACAddr:              Source MAC address of the last send data frame
        
        @type destMACAddr:              MAC address (String)
        @param destMACAddr:             Destination MAC address of the last send data frame

        @type providedPriority:         Integer
        @param providedPriority:        Priority of Data (TID: 0-15).

        @type providedServiceClass:     Boolean
        @param providedServiceClass:    Service Class of Data (True = QoSAck, False = QoSNoAck)

        @rtype:                         None
        @return:                        None
        """
        
        #Inform upper layer
        self._upperLayers[0].sendStatus(txStatus, srcMACAddr, destMACAddr, providedPriority, providedServiceClass)
        
     
        
            
class PseudoNW:
    """
    Simule a simple Network layer with a MTU = 1500 octets and the link between
    the LLC and the application layer (source or sink)
    
    This layer is not attached with devices, but with Host. The upperlayer
    will be a traffic sink or a traffic source.
    """
    
    _MTU = 2000  #IP MTU = 1500
    
    def __init__(self):
        self._host = None
        """Host on which the NW layer is installed."""
        self._device = None
        """Device on which the NW layer is installed."""
        
        self._upperLayer = None
        self._lowerLayer = None
        self._srcMAC = None
        self._dstMAC = None
        self._serviceClass = None
        self._fullName = None
        

    def setSrcMAC(self, mac):
        self._srcMAC = mac


    def setDstMAC(self, mac):
        self._dstMAC = mac
        
        
    def setServiceClass(self, serviceClass):
        self._serviceClass = serviceClass


    def registerLowerLayer(self, lowEntity):
        self._lowerLayer = lowEntity
        self._device = lowEntity._device


    def registerUpperLayer(self, upEntity):
        self._upperLayer = upEntity


    def install(self, host, protocolName):
        self._fullName = host.hostname + "." + protocolName
        self._host = host


    def send(self, bitstream, priority):
        if len(bitstream) > self._MTU:
            bitstream = bitstream[:self._MTU]

        if (self._srcMAC == None) or (self._dstMAC == None):
            raise ValueError("Frame send: Address (Source/Destination) is not attribued.")

        self._lowerLayer.send(bitstream, self._srcMAC, self._dstMAC,
                             priority, self._serviceClass)

    def sendStatus(self, txStatus, srcMACAddr, destMACAddr, providedPriority, providedServiceClass):
        #@@@The transmission status is not transmit more high
        return

    
    def receive(self, bitstream, srcMACAddr, destMACAddr, priority, serviceClass):
        if self._upperLayer:
            self._upperLayer.receive(bitstream, priority)
        

    
    
    
    
        
