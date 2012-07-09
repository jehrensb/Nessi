# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: June 2003

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

#
# Todo
# ----
# Maybe include setSrcAddress as management interface into DLBottom and DLTop.
# See Ethernet.

"""
Interface definitions of network elements: nodes, nius, media, protcols, etc.

Specific network elements, like a point-to-point link or protocol entities
have to implement these interfaces.
"""

__all__ = ["Node", "Device", "NIU", "Medium", "ProtocolEntity", "PhyLayer",
           "DLBottom", "DLTop"]


class Node(object):
    """Interface class for network nodes like hosts, switches, etc."""

    hostname = None
    """Name of the node for protocols and nodes. Type:String."""
    devices = None
    """List of network devices of the node. Type: List of Device."""

    def __init__(self):
        """Initialize the node data structures like its devices, name, etc."""
        virtual

    def addDevice(self, dev, devname):
        """Add a new network device to the node under the devicename.

        After attaching, the device is accessible as a public data member of
        the node with devname as attribute name. It is also registered
        in the devices list of the node.
        The method calls dev.setNode of the device to inform it.

        Arguments:
          dev:Device
          devname:String
        Return value:None.
        """
        virtual
        
    def addProtocol(self, protocolEntity, protoName):
        """Add a new protocol entity to the node under the given name.

        After adding, the protocol entity is accessible as a public data
        member of the node with the protoName as attribute name.
        The method calls protocolEntity.install to give the protocol
        the possibility to initialize itself.

        Arguments:
          protocolEntity : ProtocolEntity
          protoName : String
        Return value : None.
        """
        virtual

class Device(object):
    """Interface class for network devices.

    A device can be an NIU or a virtual device like a tunnel or loopback
    interface. It has an attribute 'dl' (data link protocol entity) that
    allows an upper layer protocol to transmit data over the device. A
    protocol entity has to be registered under this attribute name to
    handle packets from upper layer. An upper layer protocol calls
    device.dl.send(...) to transmit a PDU over the device.
    """
    node = None
    """Node to which the NIU is attached. Type:Node."""
    dl = None
    """Protocol entity for handling to handle send calls to the device."""
    devicename = None
    """Name under which the NIU is accessible at the node."""
    fullName = ""
    """Fully qualified name, like h1.eth1."""
    XOFF = True
    """If True, the NW layer may not call the send method of the dl to send
    a new packet. Set by DLBottom."""
    
    def __init__(self):
        """Initialize the devices data structures like node or name."""
        virtual
        
    def setNode(self, node, devicename):
        """Attach the device to a node.

        Arguments:
          node : Node -- The node to which the device is attached.
          devicename : String -- Name of the device, e.g. 'lo'.
        """
        virtual

    def addProtocol(self, protocolEntity, protocolName):
        """Add a new protocol entity to the device.

        After installing, the protocol entity is accessible as a public
        data member of the device with the protocolName as name (e.g., phy,
        mac, dl). At least a protocol named 'dl' (data link) must be installed
        on the device.

        Arguments:
          protocolEntity : ProtocolEntity
          protocolName : String
        """
        virtual
        

class NIU(Device):
    """Interface class of a Network Interface Unit, like an Ethernet NIC.

    A NIU contains the drivers for a network interface. It is attached
    to a medium, e.g., a point-to-point link or a bus. It has at least
    an attribute NIU.phy that contains the protocol entity of the
    physical layer and that communicates with the medium. Since it is
    derived from the Device base class, it also needs a NIU.dl
    protocol entity that upper layer protocols use to transmit data
    over the NIU (by calling NIU.dl.send). It may contain other protocol
    entities (like a MAC), up to the data link layer, thus all the
    protocol entities that are specific for the network interface and not for
    the node.
    """

    dl = None
    """Protocol entity for handling to handle send calls to the device."""
    phy = None
    """Protocol entity of the physical layer. Type:ProtocolEntity."""
    medium = None
    """Physical medium to which the NIU is attached. Type:Medium."""
    devicename = None
    """Name under which the NIU is accessible at the node."""
    _node = None
    """Node to which the NIU is attached. Type:Node."""
    fullName = ""
    """Fully qualified name, like h1.eth1."""

    def __init__(self):
        """Initialize the NIUs data structures."""
        virtual
        
    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        virtual
        
    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.
        
        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None.
        """
        virtual


class Medium(object):
    """Abstract base class of a physical transmission medium.

    A medium simulates the physical transmission channel like a point-to-point
    link, a bus, or a radio channel. Its main function is to accept data from
    the connected NIUs and deliver the data to receiving NIUs after a
    propagation delay. Additionally, it may simulate bit errors.
    """

    _niuDict = None
    """Dictionary of attached NIUs. Type Dict: name:String --> niu:NIU."""
    signalSpeed = 3e8
    """Propagation speed of the signal on the medium. In meters/second."""

    def __init__(self):
        """Initialize the data structures of the medium."""
        virtual

    def attachNIU(self, niu, position):
        """Attachs a NIU to the medium.

        Called by the NIU during the configuration phase of the network to
        attach itself to the medium at a given position (e.g., at one-,
        two- or three-dimensional coordinates.

        Arguments:
          niu:NIU -- NIU that attaches itself to the medium.
          position:PositionType -- Coordinates of the NIU on the medium.
        Return value: None.
        """
        virtual

    def startTransmission(self, txNIU):
        """Start a new transmission on the medium.

        A phy protocol entity calls this method to indicate that it starts
        the transmission of a signal. The medium can propagate the signal
        to other phy layer entities of connected NIUs by calling their method
        phy.newChannelActivity. By that, it can inform the entity that the
        channel is occupied. No data is actually transmitted. This will be
        done by the function completeTransmission, which is called by the phy
        layer entity at the end of the transmission.

        Arguments:
          txNIU:NIU -- Transmitting NIU
        Return value: None.
        """
        virtual

    def completeTransmission(self, txNIU, data):
        """Finish a transmission and deliver the data to receiving NIUs.

        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        delivered, after a propagation delay and possibly after introducing
        bit errors, to the phy entities of attached NIUs by calling
        phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """
        virtual


class ProtocolEntity(object):
    """Interface class for protocol entities.
    
    A protocol entity is an active entity that communicates with peer
    entities to exchange messages. It provides services to higher layer
    protocol entities and uses the services of lower layer protocol entities.

    A protocol entity has to implement at least the following methods:
      install -- Initialize the protocol when installed on a node or device.
      send -- Called from upper layer protocols to transmit a PDU.
      receive -- Called from lower layer protocols to receive a PDU.
    """

    fullName = ""
    """Fully qualified name, like h1.ip."""

    def install(self, hostOrDev, protocolName):
        """Install the protocol entity on a node or device.

        This method is called by the node or a device to inform the protocol
        that is has been installed. It performs all the initialization
        necessary for the protocol, e.g., creation of prototype packets
        that can be cloned.

        Arguments:
          hostOrDev:(Node or Device) -- Node/device on which self is installed
          protocolName:String -- Name under which self is installed on the
                                  host or device.
        Return value: None.
        """
        virtual

    def send(self, bitstream, **ici):
        """Process the outgoing packet data from an upper protocol layer.

        In the simplest case, this method has to create a new PDU object
        with the appropriate headers, add the bitstream data of the upper
        layer protocol, find a lower layer protocol entity to transmit the
        data, serialize the PDU and pass the result to the send method
        of the lower layer protocol.

        Arguments:
          bitstream:Bitstream -- Packet data the upper layer wants to send.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return value: None.
        """
        virtual

    def receive(self, bitstream, **ici):
        """Process the incoming packet data from a lower protocol layer.

        In the simplest case, this method has to fill the bitstream into
        a PDU, check the packet, find the upper layer to which the PDU has
        to be passed and call the receive method of the upper layer with
        the payload of the PDU.

        Arguments:
          bitstream:Bitstream -- Packet data from the lower protocol layer.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return result: None.
        """
        virtual


class PhyLayer(ProtocolEntity):
    """Abstract base class for a physical layer protocol entity.

    In difference to other protocol entities, a physical layer entity
    is not concerned about PDUs but only transmits a bitstream onto the
    medium. It can only be installed into a NIU but not a device, since
    devices (ie. virtual interfaces) do not have an actual physical layer.
    The physical layer does not have to register with the medium or the
    higher protocol layers. It is accessible under the attribute name '.phy'
    of its NIU. If the higher protocol entity or the medium knows the NIU,
    it can thus access its physical layer entity.

    For convenience, this abstract base class already provides an
    implementation of the method install, since is should be identical for
    all derived classes.
    """

    _niu = None
    """NIU to which the protocol entity is attached."""

    def install(self, niu, protocolName):
        """Install the physical layer protocol on a NIU.

        This method is called by a NIU (not a device) to inform the protocol
        that is has been installed. It performs all the initialization
        necessary for the protocol entity.

        Arguments:
          niu:NIU -- Network interface unit on which self is installed
          protocolName:String -- Name under which self is installed on the
                                 NIU.
        Return value: None.
        """
        if isinstance(niu, NIU):
            self._niu = niu
        else:
            raise TypeError("PhyLayer entity must be installed on a NIU")
        if protocolName != "phy":
            raise NameError("PhyLayer entity must be installed under "
                            "the name 'phy'")
        self._protocolName = "phy"
        self.fullName = niu.fullName + ".phy"

    def newChannelActivity(self):
        """Called by the medium when another NIU starts transmitting. 

        The PhyLayer entity has to implement the correct behaviour to this
        signal, depending on whether it's full duplex or half duplex PHY.
        A full duplex point-to-point link will typically ignore
        this signal. A half duplex or multiple access PHY may inform the MAC
        layer of the channel activity.
        """
        virtual

    def send(self, bitstream, **ici):
        """Send the data over the transmission medium.

        After completion, inform the upper layer (which may be a MAC protocol
        entity or a dl entity, that the transmission of the data is completed
        by calling its sendStatus method.
        
        Arguments:
          bitstream:Bitstream -- Block of data to transmit onto the medium.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return value: None.
        """
        virtual

    def receive(self, bitstream):
        """Process the incoming data from the medium.

        Called by the medium when the transmission of an NIU ends. 
        The PhyLayer entity has to implement the actions to deliver the data 
        to the upper layers.

        Arguments:
          bitstream:Bitstream -- Binary data from the medium
        Return result: None.
        """
        virtual


class DLBottom(ProtocolEntity):
    """Interface class of the lower half of the data link layer.

    The complete interface of the DL layer is split in two halfs to allow
    the creation of sublayers like LLC and MAC.
    This class defines the interface for the communication of the DL layer
    with the PHY layer. DL layer entities and MAC entities must implement
    this interface.
    """
    
    _device = None
    """Device to which the protocol entity is attached. Set during install."""

    _sendBuffer = None
    """Buffer that contains the packets given to PHY whose transmission is not
    yet confirmed."""

    def install(self,device,protocolName):
        """Install the protocol entity on a device.

        This method is called by the node or a device to inform the protocol
        that is has been installed. It performs all the initialization
        necessary for the protocol, e.g., creation of prototype packets
        that can be cloned.

        Initialize the XOFF flag of the device to indicate whether a new
        frame can be accepted from the NW layer for transmission.

        Arguments:
          device:Device -- Network device on which self is installed
          protocolName:String -- Name under which self is installed on the
                                 device.
        Return value: None.
        """
        virtual
        
    def send(self, bitstream, **ici):
        """Pass the bitstream to the PHY.

        Before sending it to PHY, place it into the sendBuffer such that
        it may be retransmitted if there is an error at the PHY.
        Set XOFF of the device to signal to the NW layer if a another
        frame can be accepted for transmission.

        This function must not be called if XOFF of the device is True, since
        in this case the DLBottom cannot accept another frame for transmission.

        Arguments:
          bitstream:Bitstream -- Block of data to transmit.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return value: None.
        """
        virtual

    def receive(self, bitstream, **ici):
        """Receive data from the phy.

        Place it into a PDU, maybe check if it is correct, and pass the
        PDU to the top DL sublayer.

        Arguments:
          bitstream:Bitstream -- Binary data from the lower protocol layer.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return result: None.
        """
        virtual

    def sendStatus(self, status, bitstream):
        """Called by the PHY at the end of a transmission.

        The status indicates if the transmission was successful or if
        there was an error.
        Set the XOFF flag of the device to indicate if a new frame
        can be accepted for transmission.

        Arguments:
          status:Integer -- indicates success or failure of the transmission.
          bitstream:Bitstream -- Data that should be send (via phy.send)
        """
        virtual
        

class DLTop(ProtocolEntity):
    """Interface class of the upper half of the data link layer.

    The complete interface of the DL layer is split in two halfs to allow
    the creation of sublayers like LLC and MAC.
    This class defines the interface for the communication of the DL layer
    with the network layer. DL layer entities and LLC entities must implement
    this interface.
    """

    _device = None
    """Device to which the protocol entity is attached. Set during install."""
    _upperLayers = None
    """Dictionary: protocolType -> Upper layer protocol entity."""

    def __init__(self):
        self._upperLayers = {}

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
        virtual

    def send(self, bitstream, **ici):
        """Accept a bitstream from the NW layer and try to send it.

        Pass it to DLBottom.send to transmit it.

        This function may only be called if flag XOFF of the device is False,
        i.e. if the DLBottom can accept a new frame.

        Arguments:
          bitstream: Bitstream -- Data to transmit
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return value:
          status: 0 -- Indicates that the packet has been queued with success
                  other -- Indicates other reasons why the packet has not
                           been sent.
        """
        virtual

    def receive(self,pdu, **ici):
        """Accept a pdu from the DLBottom. Analyze the packet header and
        demultiplex it accordingly to the upper layer protocols.

        Arguments:
          pdu:PDU -- PDU received from the lower DL sublayer.
          ici:Dictionary -- Interface control information for additional
                            parameters, if required.
        Return result: None.
        """
        virtual

    def sendStatus(self, status, bitstream):
        """Called by DLBottom at the end of a transmission.

        The status indicates if the transmission was successful or if
        there was an error.
        Maybe retransmit the frame (if the DL is reliable) or inform the NW
        layer.

        Arguments:
          status:Integer -- indicates success or failure of the transmission.
          bitstream:Bitstream -- Data that was tried to be sent
        """
        virtual


class HigherLayerProtocol(ProtocolEntity):
    """Interface class of protocol entities of layer 3 to 7.

    Additionally to the normal methods, higher layer protocols provide
    register methods to register with upper and lower layer protocol entities.
    Received packet are passed to upper layer entities.
    Packets to transmit are passed to lower layer entities.
    """

    _upperLayers = None
    """Dictionary: protocolType -> Upper layer protocol entity."""
    _lowerLayers = None
    """Data structure that contains the lower layer protocol entities."""

    def __init__(self):
        self._upperLayers = {}

    def registerUpperLayer(self, upperProtocolEntity, protocolType):
        """Register an upper layer protocol to receive packet.

        If a received packet matches the protocolType, it is delivered to
        the upper layer protocol by calling its receive function.
        protocolType may be a numeric type or None to indicate that the
        protocol wants to receive all packets.
        This information is stored in the _upperLayers data member.

        Arguments:
          upperProtocolEntity:ProtocolEntity -- receiver of packets
          protocolType:Numeric or None: criterion which packets should be
                                        passed to the upper layer protocol.
        Return value: None.
        """
        virtual

    def registerLowerLayer(self, lowerProtocolEntity, *args):
        """Register a lower layer protocol entity to transmit packets to.

        If several lower layer protocols may be registered, this function has
        to examine the lower layer entities to find out more about their
        characteristics (e.g., offered service, MAC address, ...).
        This information can then be stored in the _lowerLayers data member.

        Arguments:
          lowerProtocolEntity:ProtocolEntity -- entity that can send packets
          args:AnyType -- additional criteria when to use this entity.
        Return value: None
        """
        virtual
