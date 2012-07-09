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
This module define variables and constants for use in IEEE 802.11e:
    - PHY Modulation
    - MAC MIB (Management Information Base)
    - MAC BIB (BSS Information Base)
    - MAC Backoff Entity
    - MAC EDCA Table
    - MAC HC (Hybrid Coordinator)
    - MAC Statistics
    - MAC Enumeration (MacFrameType, MacFrameSubType, MacState, MacStatus)
    - MAC Frame Format
"""


__all__ = ["PhyModulation", "MacMIB", "BackoffEntity", "EDCATable", "BSSInfoBase", "HC", "MacStat", "MacFrameType",\
"MacFrameSubType", "MacState", "MacStatus", "MacFrameFormat", "sqrtint"]


from random import random
from pdu import formatFactory



class PhyModulation:
    """
    The attributes defined in this class corresponds to the constants of
    the 3 differents modulations employed for 802.11, 802.11b and 802.11g:
        - FHSS (default value)
        - DSSS
        - OFDM
    """
    
    def __init__(self):
        """FHSS is the default value (for 1 Mbps)"""

        self.sifsTime = 28e-6
        """
        The time that the MAC and PHY will require to receive the last symbol of a frame,
        process the frame, and respond with a first symbol on the air interface.
        aSIFSTimea = RxRFDelay + aRxPLCPDelay + aMACProcessingDelay + aRxTxTurnaroundTime
        
        Type: Float
        """
        
        self.slotTime = 50e-6
        """
        Base time unit to calculate time variables in MAC level.
        aSlotTime = aCCATime + aRxTxTurnaroundTime + aAirPropagationTime + aMACProcessingDelay
        
        Type: Float
        """
        
        self.cwMin = 15
        """
        Minimum size of the contention window (in SlotTime).
        
        Type: Integer
        """
        
        self.cwMax = 1023
        """
        Maximum size of the contention window (in SlotTime).
        
        Type: Integer
        """
        
        self.preambleLength = 96e-6
        """
        The current PHY PLCP Preamble Length (96 bits). Always transmit at 1 Mbps for FHSS.
        
        Type: Float
        """
        
        self.plcpHeaderLength = 32e-6
        """
        The current PHYs PLCP Header Length (32 bits).
        Always transmit at 1 Mbps for FHSS.
        
        Type: Float
        """
        
        
        #Others PHY constants 802.11 FHSS (Not use)
        """
        self.CCATime = 27e-6
        self.MPDUMaxLength = 4095
        self.RxRFDelay = 4e-6
        self.RxPLCPDelay = 2e-6
        self.MACProcessingDelay = 2e-6
        self.RxTxTurnaroundTime = 20e-6
        self.AirPropagationTime = 1e-6
        self.TxPLCPDelay = 1e-6
        self.RxTxSwitchTime = 10e-6
        self.TxRampOnTime = 8e-6
        self.TxRampOffTime = 8e-6
        self.TxRFDelay = 1e-6
        self.MPDUDurationFactor = 31250000
        """



    def FHSS(self):
        """FHSS constants (section 14.9)"""
        self.__init__()
        
        
    def DSSS(self):
        """DSSS constants (section 18.3.4)"""
        self.slotTime = 20e-6
        self.sifsTime = 10e-6
        self.cwMin = 31
        self.cwMax = 1023
        self.preambleLength = 144e-6 # 144 bits at 1 Mbps
        self.plcpHeaderLength = 48e-6 # 48 bits at 1 Mbps
        
        
    def OFDM(self):
        """OFDM (shorts constants is used) (section 19.8.4)"""
        self.slotTime = 9e-6
        self.sifsTime = 10e-6
        self.cwMin = 31
        self.cwMax = 1023
        self.preambleLength = 20e-6
        self.plcpHeaderLength = 4e-6
        
    



class MacMIB:
    """
    Definition of Management Information Base (MIB) of MAC layer. The variables
    contened in the MAC MIB provides the necessary support for the access control,
    generation, and verification of frame check sequences, and proper delivery
    of valid data to upper layers. (Annexe D in standard IEEE 802.11)
    
    The MAC statistics variables is not contained in this class, but they are
    defined in an another: class MacStat.
    """
    
    def __init__(self):
    
    
        self.address = None
        """
        Unique MAC Address assigned to the STA.
        
        Type: MAC address (String)
        
        Synthax: ex: '20:C0:83:AD:33:01'
                
        Default Value: None     
        """
    
    
        self.rtsThreshold = 2347
        """
        This attribute shall indicate the number of octets in an MPDU,
        below which an RTS/CTS handshake shall not be performed. An
        RTS/CTS handshake shall be performed at the beginning of any
        frame exchange sequence where the MPDU is of type Data or
        Management, the MPDU has an individual address in the Address1
        field, and the length of the MPDU is greater than
        this threshold. (For additional details, refer to Table 21 in
        9.7.) Setting this attribute to be larger than the maximum
        MSDU size shall have the effect of turning off the RTS/CTS
        handshake for frames of Data or Management type transmitted by
        this STA. Setting this attribute to zero shall have the effect
        of turning on the RTS/CTS handshake for all frames of Data or
        Management type transmitted by this STA.
        
        Type: Integer
        
        Synthax: 0 - 2347
        
        Default Value: 2347
        """
    
    
        self.shortRetryLimit = 7
        """
        This attribute shall indicate the maximum number of
        transmission attempts of a frame, the length of which is less
        than or equal to RTSThreshold, that shall be made before a
        failure condition is indicated.
        
        Type: Integer
        
        Synthax: 1 - 255
        
        Default Value: 7
        """
    
    
        self.longRetryLimit = 4
        """
        This attribute shall indicate the maximum number of
        transmission attempts of a frame, the length of which is
        greater than RTSThreshold, that shall be made before a
        failure condition is indicated.
        
        Type: Integer
        
        Synthax: 1 - 255
        
        Default Value: 4
        """
        
        
        self.fragmentationThreshold = 2346
        """
        This attribute shall specify the current maximum size, in
        octets, of the MPDU that may be delivered to the PHY. An MSDU
        shall be broken into fragments if its size exceeds the value
        of this attribute after adding MAC headers and trailers. An
        MSDU or MMPDU shall be fragmented when the resulting frame has
        an individual address in the Address1 field, and the length of
        the frame is larger than this threshold.

        Type: Integer
        
        Synthax: 256 - 2346
        
        Default Value: 2346
        """
        
    
        self.maxTransmitMSDULifetime = 512
        """
        The MaxTransmitMSDULifetime shall be the elapsed time in TU,
        after the initial transmission of an MSDU, after which further
        attempts to transmit the MSDU shall be terminated.

        Type: Integer
        
        Synthax: 1 - 4294967295
        
        Default Value: 512
        """
        
        
        self.maxReceiveLifetime = 512
        """
        The MaxReceiveLifetime shall be the elapsed time in TU,
        after the initial reception of a fragmented MMPDU or MSDU,
        after which further attempts to reassemble the MMPDU or
        MSDU shall be terminated.

        Type: Integer
        
        Synthax: 1 - 4294967295
        
        Default Value: 512
        """
    
    
    
    def reset(self):
        """
        Reset the MIB with the default values and with a new MAC address
        
        @rtype:     None
        @return:    None
        """

        self.__init__()
        self.address = self.macAddrGen() #Init MAC Address



    def macAddrGen(self):
        """
        Generate a random MAC address (48 bits)
        
        @rtype:     MAC Address (String)
        @return:    Random MAC Address
        """
    
        ints = [int(random()*256) for i in range(6)]
        if ints[0]%2 == 1: #The first number of address is pair (not multicast)
            ints[0] -= 1
        return "%02X:%02X:%02X:%02X:%02X:%02X"%tuple(ints)



class BackoffEntity:
    """
    A Backoff Entity is defined across many variables and a transmission queue.
    With DCF STA or AP have 1 Backoff Entity: DCF

    With EDCA every QSTA or QAP have 4 Backoff Entities:
        - AC_BE
        - AC_BK
        - AC_VI
        - AC_VO
        
    The following information must be provide by the MAC sublayer
    to fixe the EDCA parameter:
        - Name of Backoff Entity
        - cwMin PHY reference
        - cwMax PHY reference
        - PHY DataRate
    """
    
    def __init__(self, name, cwMin, cwMax, dataRate):
    
        self.name = name
        """Name of the Backoff Entity: AC_BE, AC_BK, AC_VI, AC_VO or DCF."""
        
        self.EDCATable = EDCATable(name, cwMin, cwMax, dataRate)
        """
        Conceptual table for EDCA default parameter values at a non-AP QSTA
        for the selected Access Category.
        """
    
        self.transmissionQueue = []
        """Queue of MSDU transmission."""
        
        self.remainBackoffCTR = 0 #[TU]
        """Time Unit remaining of the current Backoff. Use for the next transmision attempt."""
        
        self.shortRetryCount = 0
        """Attempts to retransmit a short sequence (STA Short Retry Count = SSRC)."""
       
       
       
    def resetEDCATable (self, name, cwMin, cwMax, dataRate):
        """
        Reset the EDCATable with the current values in use of the PHY layer.

        @type cwMin:        Integer
        @param cwMin:       Minimum Contention Window defined in PHY layer.

        @type cwMax:        Integer
        @param cwMax:       Maximum Contention Window defined in PHY layer.
        
        @type dataRate:     Integer
        @param dataRate:    Data rate used in PHY layer for transmision.

        @rtype:             None
        @return:            None
        """
    
        self.EDCATable = EDCATable(name, cwMin, cwMax, dataRate)
        
        
class EDCATable:
    """
    Conceptual table for EDCA default parameter values at a non-AP
    QSTA. This table shall contain the four entries of the EDCA
    parameters corresponding to four possible ACs. There are 4
    ACs (parameter name):
        - AC_BK
        - AC_BE
        - AC_VI
        - AC_VO
    """
    
    def __init__(self, name, cwMin, cwMax, dataRate):
      
        self.CWmin = None
        """
        This attribute shall specify the value of the minimum size of the
        window that shall be used by a QSTA for a particular AC for
        generating a random number for the backoff. The value of this
        attribute shall be such that it could always be expressed in the
        form of 2X - 1, where X is an integer. The default value is calculed
        with the cwMin defined by the PHY layer.

        Type: Integer
        
        Synthax: 0 - 255
        
        Default Value:
            1)  cwMin for AC_BK and AC_BE.
            2) (cwMin+1)/2 - 1 for AC_VI.
            3) (aCWmin+1)/4 - 1 for AC_VO.
        """
        
        
        self.CWmax = None
        """
        This attribute shall specify the value of the maximum size of the
        window that shall be used by a QSTA for a particular AC for
        generating a random number for the backoff. The value of this
        attribute shall be such that it could always be expressed in the
        form of 2X -1, where X is an integer.The default value is calculed
        with the cwMin and cwMax defined by the PHY layer.

        Type: Integer
        
        Synthax: 0 - 65535
        
        Default Value:
            1) cwMax for AC_BK and AC_BE.
            2) cwMin for AC_VI.
            3) (cwMmin+1)/2 - 1 for AC_VO.
        """
        
        
        self.AIFSN = None
        """
        This attribute shall specify the number of slots, after a SIFS
        duration, that the QSTA, for a particular AC, shall sense the
        medium idle either before transmitting or executing a backoff.

        Type: Integer
        
        Synthax: 2 - 15
        
        Default Value:
            1) 7 for AC_BK.
            2) 3 for AC_BE.
            3) 2 for AC_VI and AC_VO.
        """
        
        
        
        self.TXOPLimit = None
        """
        This attribute shall specify the maximum number of microseconds of
        an EDCA TXOP for a given AC at a non-AP QSTA.
        
        Type: Integer
        
        Synthax: 0 - 65535
        
        Default Value:
            1) 0 for all PHYs (AC_BK and AC_BE); this
                implies that the sender can send one MSDU in an EDCA TXOP
            2) 3008 microseconds for IEEE 802.11a/g PHY and 6016
                microseconds for IEEE 802.11b PHY (AC_VI).
            3) 1504 microseconds for IEEE 802.11a/g PHY and 3264
                microseconds for IEEE 802.11b PHY (AC_VO).
        """
        
        
        
        
        self.MSDULifeTime = 500
        """
        This attribute shall specify (in TUs) the maximum duration an
        MSDU, for a given AC, would be retained by the MAC before it is
        discarded.

        Type: Integer
        
        Synthax: 0 - 500
        
        Default Value: 500
        """
        
        
        if name == "AC_BK":
        
            self.CWmin = cwMin
            self.CWmax = cwMax
            self.AIFSN = 7
            self.TXOPLimit = 0
        
        elif name == "AC_BE":
        
            self.CWmin = cwMin
            self.CWmax = cwMax
            self.AIFSN = 3
            self.TXOPLimit = 1000
            
        elif name == "AC_VI":
        
            self.CWmin = (cwMin+1)/2 - 1
            self.CWmax = cwMax
            self.AIFSN = 2
            
            if dataRate in (1e6, 2e6): #802.11
                self.TXOPLimit = 0
        
            elif dataRate in (5.5e6, 11e6): #802.11b
                self.TXOPLimit = 6016
        
            else: #802.11a/g
                self.TXOPLimit = 3008
             
        elif name == "AC_VO":
        
            self.CWmin = (cwMin+1)/4 - 1
            self.CWmax = (cwMin+1)/2 - 1
            self.AIFSN = 2
            
            if dataRate in (1e6, 2e6): #802.11
                self.TXOPLimit = 0
        
            elif dataRate in (5.5e6, 11e6): #802.11b
                self.TXOPLimit = 3264
        
            else: #802.11a/g
                self.TXOPLimit = 1504
                
                
        elif name == "DCF":
        
            self.CWmin = cwMin
            self.CWmax = cwMax
            self.AIFSN = 2 # => DIFS
            self.TXOPLimit = 0
        
            
        else:
            raise ValueError("Name Error for EDCATable.")
    
    
    
    


class BSSInfoBase:
    """
    This class regroup the information of the BSS. The attributs are update with
    the information contened in the Beacon frame (and with the operation of scan,
    authenticate and association).
    
    This class is not compliant with the stantard (BSSInfoBase doesn't exist).
    """

    def __init__(self):
    
        self.bssId = "00:02:00:02:00:02"
        """
        MAC address of the BSS (BSS ID).
        
        Type: MAC Address (String)

        Default Value: "00:02:04:06:08:0A"
        """
  
  
        self.apAddr = "00:02:04:06:08:0A"
        """
        MAC address of the Access Point.
        
        Type: MAC Address (String)

        Default Value: "00:02:04:06:08:0A"
        """
        
        
        self.staAddr = []
        """
        List of MAC address of all (Q)STA in BSS. Only for the QAP.
        
        Type: List of MAC Address (String)

        Default Value: ""
        """
  
  
        self.beaconInterval = 5000
        """
        Time between two Beacons frame in TU.

        Type: Integer

        Synthax: 1 - 65535

        Default Value: 5000
        """
    
    
        self.dtim = 200
        """
        Time correspond to the next opportunity to receive multicast and
        broadcast messages
    
        Type: Integer

        Synthax: 1 - 255

        Default Value: 200
        """
    
        #@@@ To be continued


        
class HC:
    """
    Class use for the management of the Hybrid Coordinator (us only in HCCA). The HC is
    present only in a QAP.
    """
    
    def __init__(self):
        self.nbSta = 0
        """Number of QSTA in QBSS."""
        self.nbMsduMax = 3
        """The number limit of MSDUs in transmission queue to obtain a CFP and a CAP."""
        self.queueSize = {}
        """Dic: Size of transmission queue per AC [AC_BE, AC_BK, AC_VI, AC_VO] of all QSTA.
           The key correspond to the address MAC of the QSTA"""

    
    
    def applyCFP(self):
        """
        Take a decision about the application of a CFP for the next
        superframe.
    
        @rtype:     Boolean
        @return:    Decision about the application of the CFP.
        """
        
        #If an AC transmission queue have 'nbMSDUmax' or more MSDU in waiting, the CFP is apply.
        for sta in self.queueSize.values():
            for ac in sta:
                if ac >= self.nbMsduMax:
                    return True

        return False
    
    
    
    def selectAC(self):
        """
        Determine the prioritest AC in the QBSS in function of:
            - Priority of AC
	        - Length of transmissions queues of AC
	        - Length of transmissions queues by QSTA
            - (Duration of TXOP available)
            
        Return a tuple null if the HC have not found a transmission queue
        with enough MSDU in waiting.
        
        TODO: Optimize to create a list of all CAP possible (Size Queue must be
        larger than self.nbMsduMax) 
        
        @rtype:     Tuple
        @return:    Address MAC of the QSTA selected with the TID
        """
        
        addrSelected = None
        acIndexSelected = None
  
        if not self.queueSize:
            return (0,0)
        
        priority = 0
        acSizeQueue = 0
        totalSizeQueue = 0
        
        for sta in self.queueSize:
            index = 0
            for ac in self.queueSize[sta]:
                index += 1
                if ac >= self.nbMsduMax:
                
                    #1.PRIORITY
                    if index > priority:
                        priority = index
                        acSizeQueue = ac
                        totalSizeQueue = self.queueSize[sta][0] + self.queueSize[sta][1]\
                        + self.queueSize[sta][2] + self.queueSize[sta][3]
                        
                        #Save the address and the AC index
                        addrSelected = sta
                        acIndexSelected = index
                    
                    elif index == priority:

                        #2.AC SIZE QUEUE
                        if ac > acSizeQueue:
                            priority = index
                            acSizeQueue = ac
                            totalSizeQueue = self.queueSize[sta][0] + self.queueSize[sta][1]\
                            + self.queueSize[sta][2] + self.queueSize[sta][3]
                            
                            #Save the address and the AC index
                            addrSelected = sta
                            acIndexSelected = index
                            
                        elif ac == acSizeQueue:
                        
                            #3.TOTAL AC SIZE QUEUE
                            actualTotalSizeQueue = self.queueSize[sta][0] + self.queueSize[sta][1]\
                            + self.queueSize[sta][2] + self.queueSize[sta][3]
                            if actualTotalSizeQueue > totalSizeQueue:
                                priority = index
                                acSizeQueue = ac
                                totalSizeQueue = actualTotalSizeQueue
                                
                                #Save the address and the AC index
                                addrSelected = sta
                                acIndexSelected = index
                                
                            #if actualTotalSizeQueue == totalSizeQueue we keep the first AC found
                         
            
        if not addrSelected:
            return (0,0)
        
        if acIndexSelected == 0: #AC_BE
            tidSelected  = 0
        
        elif acIndexSelected == 1: #AC_BK
            tidSelected  = 1
        
        elif acIndexSelected == 2: #AC_VI
            tidSelected  = 3
        
        elif acIndexSelected == 3: #AC_VO
            tidSelected  = 6
        
        else:
            raise ValueError("Invalid index for AC.")
    
        return (addrSelected, tidSelected)


        
        
class MacStat:
    """
    Class use for the management of statistics variables for in MAC 802.11 layer.
    """

    def __init__(self):

        self.framesTransmittedOK = 0
        """Number of data frames that are successfully transmitted (acknowledged)."""
        self.framesRetransmitted = 0
        """Total number of data frames retransmissions."""
        self.ackTransmit = 0
        """Total number of ACK frames sent."""
        self.cfPollTransmit = 0
        """Total number of QoS CF-Poll frames sent."""
        self.cfEndTransmit = 0
        """Total number of CF-End frames sent."""
        self.beaconTransmit = 0
        """Total number of Beacon frames sent."""
        self.framesAborded = 0
        """Count of aborded data frames due to a many number of retransmission."""
        self.msduDeleted = 0
        """Count of MSDUs deleted of the transmission queue."""

        self.framesReceivedOK = 0
        """Number of data frames that are successfully received."""
        self.framesReceivedFCSErrors = 0
        """Count of received data frames that did not pass the FCS check."""
        self.duplicateFramesReceived = 0
        """Number of same data frames received (possible if ACKs are corrupted)."""


        self.ackReceivedOK = 0
        """Total number of ACK frames received."""
        self.ackReceivedFCSErrors = 0
        """Count of received ACK frames that did not pass the FCS check."""
        self.cfPollReceivedOK = 0
        """Total number of QoS CF-Poll frames received."""
        self.cfPollReceivedFCSErrors = 0
        """Count of received QoS CF-Poll frames that did not pass the FCS check."""
        self.cfEndReceivedFCSErrors = 0
        """Total number of CF-End frames received."""        
        self.cfEndReceivedOK = 0
        """Count of received CF-End frames that did not pass the FCS check."""        
        self.beaconReceivedOK = 0
        """Total number of Beacon frames received."""
        self.beaconReceivedFCSErrors = 0
        """Count of received Beacon frames that did not pass the FCS check."""



        self.octetsTransmittedOK = 0
        """Count of data and padding octets of successfully transmitted frames."""
        self.octetsTransmittedError = 0
        """Count of data and padding octets of failed transmitted frames."""
        self.octetsReceivedOK = 0
        """Count of data and padding octets of successfully received frames."""
        self.octetsReceivedError = 0
        """Count of data octets received with errors."""
        
        self.unknowReceivedFCSErrors = 0
        """Count of unknown receive frame due to a FCS error (impossible to determine
        frame type or destination address)."""



class MacFrameType:
    """
    Definition of the MAC Frame type (enumeration).
    """

    def __init__(self):
        self.MANAGEMENT = 0
        self.CONTROL = 1
        self.DATA = 2



class MacFrameSubType:
    """
    Definition of the MAC Frame subtype (enumeration).
    """

    def __init__(self):
        self.ASSOCIATIONREQUEST = 0
        self.ASSOCIATIONRESPONSE = 1
        self.REASSOCIATIONREQUEST = 2
        self.REASSOCIATIONRESPONSE = 3
        self.PROBEREQUEST = 4
        self.PROBERESPONSE = 5
        self.BEACON = 8
        self.ATIM = 9
        self.DISASSOCIATION = 10
        self.AUTHENTICATION = 11
        self.DEAUTHENTICATION = 12
        self.ACTION = 13
        self.BLOCKACKREQ = 8
        self.BLOCKACK = 9
        self.PS_POLL = 10
        self.RTS = 11
        self.CTS = 12
        self.ACK = 13
        self.CF_END = 14
        self.CF_END_plus_CF_ACK = 15
        self.DATA = 0
        self.DATA_plus_CF_ACK = 1
        self.DATA_plus_CF_POLL = 2
        self.DATA_plus_CF_ACK_plus_CF_POLL = 3
        self.NULL = 4
        self.CF_ACK = 5
        self.CF_POLL = 6
        self.CF_ACK_plus_CF_POLL = 7
        self.QOSDATA = 8
        self.QOSDATA_plus_CF_ACK = 9
        self.QOSDATA_plus_CF_POLL = 10
        self.QOSDATA_plus_CF_ACK_plus_CF_POLL = 11
        self.QOSNULL = 12
        self.QOSCF_POLL = 14
        self.QOSCF_ACK_plus_CF_POLL = 15



class MacState:
    """
    Definition of differents states of MAC layer (enumeration).
    """
    
    def __init__(self):
        self.IDLE = 0
        self.SEND_DATA = 1
        self.SEND_ACK = 2
        self.SEND_BEACON = 3
        self.SEND_CFPOLL = 4
        self.SEND_CFEND = 5
        self.WAIT_ACK = 6
        #self.TXOP
        #self.NAV
        #self.SEND_RTS
        #self.SEND_CTS

        
        
class MacStatus:
    """
    Definition of the MAC Status (enumeration).
    """

    def __init__(self):
        self.SUCCESS = 0
        self.FAILURE = 1
        self.UNDELIVERABLE = 2
        self.UNAVAILABLE_PRIORITY = 3
        
               

   
   
class MacFrameFormat:
    """
    Definition of formats of the three main MAC Frame:
        - Data Frame
        - Beacon Frame (management)
        - Ack frame (control)
    """
   
    def __init__(self):
    
        #Structure of the default data frame (7.2.2)
        #With QoS Control field
        self.MPDUQos = formatFactory(
        [('frameControl', 'ByteField', 16, None),
        ('durationID', 'Int', 16, 0),
        ('address1', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('address2', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('address3', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('sequenceControl', 'ByteField', 16, None),
        ('address4', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('qosControl', 'ByteField', 16, None),  #QoS capabilities
        ('data', 'ByteField', None, None),
        ('FCS', 'Int', 32, None)
        ], self)
        #Without QoS Control field
        self.MPDU = formatFactory(
        [('frameControl', 'ByteField', 16, None),
        ('durationID', 'Int', 16, 0),
        ('address1', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('address2', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('address3', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('sequenceControl', 'ByteField', 16, None),
        ('address4', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('data', 'ByteField', None, None),
        ('FCS', 'Int', 32, None)
        ], self)

   
        #QoS Control field (7.1.3.5)
        self.QosControl = formatFactory(
        [('tid', 'BitField', 4, 0),
        ('eosp', 'BitField', 1, 0),
        ('ackPolicy', 'BitField', 2, 0),
        ('reserved', 'BitField', 1, 0),
        ('txopOrQueue', 'Int', 8, None)
        ], self)
   
   
        #Frame Control field (7.1.3.1)
        self.FrameControl = formatFactory(
        [('protocolVersion', 'BitField', 2, 0),
        ('type', 'BitField', 2, None),
        ('subType', 'BitField', 4, None),
        ('toDS', 'BitField', 1, 0),
        ('fromDS', 'BitField', 1, 1),
        ('moreFrag', 'BitField', 1, 0),
        ('retry', 'BitField', 1, 0),
        ('pwrMgt', 'BitField', 1, 0),
        ('moreData', 'BitField', 1, 0),
        ('wep', 'BitField', 1, 0),
        ('order', 'BitField', 1, None)
        ], self)
        
        
        #Sequence Address field (7.1.3.4)
        self.SequenceControl = formatFactory(
        [('fragmentNb', 'BitField', 4, None),
        ('sequenceNb', 'BitField', 12, None)
        ], self)
        
        
        #Structure of the ACK frame (7.2.1.3)
        self.ACK = formatFactory(
        [('frameControl', 'ByteField', 16, None),
        ('durationID', 'Int', 16, 0),
        ('receiverAddress', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('FCS', 'Int', 32, None)
        ], self)
        
        
        #Structure of the CF-END frame (7.2.1.3)
        self.CF_END = formatFactory(
        [('frameControl', 'ByteField', 16, None),
        ('durationID', 'Int', 16, 0),
        ('receiverAddress', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('BSSID', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('FCS', 'Int', 32, None)
        ], self)
        
        
        #Structure of the default Management frame (7.2.3)
        self.Management = formatFactory(
        [('frameControl', 'ByteField', 16, None),
        ('durationID', 'Int', 16, 0),
        ('DA', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('SA', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('BSSID', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
        ('sequenceControl', 'ByteField', 16, None),
        ('data', 'ByteField', None, None),
        ('FCS', 'Int', 32, None)
        ], self)
        
        #Structure of data field for a Beacon frame (7.2.3.1)
        #With QoS
        self.BeaconDataQos = formatFactory(
        [('timeStamp', 'ByteField', 48, None),
        ('beaconInterval', 'Int', 16, None),
        ('capabilityInfo', 'ByteField', 16, None),
        ('SSID', 'ByteField', 16, None), #Variable size: 16-272 (min is employed)
        ('supportedRates', 'ByteField', 24, None), #Variable size: 24-80 (min is employed)
        #('FHParameterSet','ByteField', 56, None), #Optional (for FHSS modulation)
        #('DSParameterSet','ByteField', 16, None), #Optional (for DSSS modulation)
        #('CFParameterSet','ByteField', 64, None), #Optional (for PCF)
        #('IBSSParameterSet','ByteField', 32, None), #Optional (for independant BSS structure)
        ('TIM','ByteField', None, None),
        ('QBSSLoad', 'ByteField', 56, None), #QoS capabilities
        ('EDCAParameterSet', 'ByteField', 160, None), #QoS capabilities
        ('QosCapability', 'ByteField', 24, None) #QoS capabilities
        ], self)
        #Without QoS
        self.BeaconData = formatFactory(
        [('timeStamp', 'ByteField', 48, None),
        ('beaconInterval', 'Int', 16, None),
        ('capabilityInfo', 'ByteField', 16, None),
        ('SSID', 'ByteField', 16, None), #Variable size: 16-272 (min is employed)
        ('supportedRates', 'ByteField', 24, None), #Variable size: 24-80 (min is employed)
        ('TIM','ByteField', None, None),
        ], self)
        
        #Structure of the Capability Info field (7.3.1.4)
        self.CapabilityInfo = formatFactory(
        [('ESS', 'BitField', 1, None),
        ('IBSS', 'BitField', 1, None),
        ('CFPollable', 'BitField', 1, None),
        ('CFPollRequest', 'BitField', 1, None),
        ('privacy', 'BitField', 1, None),
        ('shortPreamble', 'BitField', 1, None),
        ('PBCC', 'BitField', 1, None),
        ('channelAgility', 'BitField', 1, None),
        ('spectrumManagement', 'BitField', 1, None),
        ('Qos', 'BitField', 1, None), #QoS capabilities
        ('shortSlotTime', 'BitField', 1, None),        
        ('APSD', 'BitField', 1, None), #QoS capabilities
        ('reserved', 'BitField', 1, None),
        ('DSSS_OFDM', 'BitField', 1, None),
        ('delayedBlockAck', 'BitField', 1, None), #QoS capabilities
        ('immediateBlockAck', 'BitField', 1, None) #QoS capabilities   
        ], self)
        
        #Element model field (7.3.2)
        self.Element = formatFactory(
        [('elementID', 'Int', 8, None),
        ('length', 'Int', 8, None),
        ('information', 'ByteField', None, None)
        ], self)
        
        #EDCA Parameter Set (Element) (7.3.2.14)
        self.EDCAParameterSet = formatFactory(
        [('QosInfo', 'ByteField', 8, None),
        ('reserved', 'ByteField', 8, None),
        ('AC_BEParameterRecord', 'ByteField', 32, None),
        ('AC_BKParameterRecord', 'ByteField', 32, None),
        ('AC_VIParameterRecord', 'ByteField', 32, None),
        ('AC_VOParameterRecord', 'ByteField', 32, None),                   
        ], self)
        
        #QoS Information subfield (from AP) (7.3.1.17)
        self.QosInformationAP = formatFactory(
        [('EDCAParamSetUpdateCount', 'BitField', 4, None),
        ('Q_Ack', 'BitField', 1, None),
        ('queueRequest', 'BitField', 1, None),
        ('TXOPRequest', 'BitField', 1, None),
        ('reserved', 'BitField', 1, None),
        ], self)
        
        #QoS Information subfield (from STA) (7.3.1.17)
        self.QosInformationSTA = formatFactory(
        [('AC_VOFlag', 'BitField', 1, None),
        ('AC_VIFlag', 'BitField', 1, None),
        ('AC_BKFlag', 'BitField', 1, None),
        ('AC_BEFlag', 'BitField', 1, None),
        ('Q_Ack', 'BitField', 1, None),
        ('maxSPLength', 'BitField', 2, None),
        ('moreDataAck', 'BitField', 1, None),
        ], self)
        
        #AC Parameter Record subfield (from STA) (7.3.2.14)
        self.ACParameterRecord = formatFactory(
        [('AIFSN', 'BitField', 4, None),
        ('ACM', 'BitField', 1, None),
        ('ACI', 'BitField', 2, None),
        ('reserved', 'BitField', 1, None),
        ('ECWmin', 'BitField', 4, None),
        ('ECWmax', 'BitField', 4, None),
        ('TXOPLimit', 'BitField', 16, None),        
        ], self)
   
   
 



"""
Define many simple method to help to process number.
"""

def sqrtint(int):
    """
    Return the square root of a puissance of 2 integer.
        
    @type int:      Integer
    @param int:     Number puissance of 2 (4, 32, 156, 1024, ...).

    @rtype:         Integer
    @return:        SQRT of parameter entry.
    """

    i=0
    while int > 1:
        int=int>>1
        i+=1
        
    return i
    
