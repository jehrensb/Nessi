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
Implementations of different device types, like NICs, virtual devices, etc.
"""

__all__ = ["NIC", "AP", "QAP", "WNIC", "QWNIC"]

from netbase import Device, NIU


class NIC(NIU):
    """
	Implementation of a simple Network Interface Card (NIC).
	"""

    def __init__(self):
        pass
        
    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        self._node = node
        self.devicename = devicename
        self.fullName = "%s.%s"%(node.hostname, devicename)

    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.
        
        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None."""

        self.medium = medium
        medium.attachNIU(self, position)

    def addProtocol(self, protocolEntity, protocolName):
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
        setattr(self, protocolName, protocolEntity)
        protocolEntity.install(self, protocolName)


class AP(NIU):
    """
	Implementation of an Access Point (AP) for a Wireless Network.
	"""

    def __init__(self):
        pass

    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        self._node = node
        self.devicename = devicename
        self.fullName = "%s.%s"%(node.hostname, devicename)

    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.

        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None."""

        self.medium = medium
        medium.attachNIU(self, position)

    def addProtocol(self, protocolEntity, protocolName):
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
        setattr(self, protocolName, protocolEntity)
        protocolEntity.install(self, protocolName)



class QAP(NIU):
    """
	Implementation of an QoS Access Point (QAP) for a QoS Wireless Network.
	"""

    def __init__(self):
        pass

    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        self._node = node
        self.devicename = devicename
        self.fullName = "%s.%s"%(node.hostname, devicename)

    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.

        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None."""

        self.medium = medium
        medium.attachNIU(self, position)

    def addProtocol(self, protocolEntity, protocolName):
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
        setattr(self, protocolName, protocolEntity)
        protocolEntity.install(self, protocolName)
        
        

class WNIC(NIU):
    """
	Implementation of an Wireless Network Interface Card (WNIC) for a Wireless Network.
	"""

    def __init__(self):
        pass

    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        self._node = node
        self.devicename = devicename
        self.fullName = "%s.%s"%(node.hostname, devicename)

    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.

        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None."""

        self.medium = medium
        medium.attachNIU(self, position)

    def addProtocol(self, protocolEntity, protocolName):
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
        setattr(self, protocolName, protocolEntity)
        protocolEntity.install(self, protocolName)




class QWNIC(NIU):
    """
	Implementation of an QoS Wireless Network Interface Card (WNIC) for a QoS Wireless Network.
	"""

    def __init__(self):
        pass

    def setNode(self, node, devicename):
        """Attach the NIU to a node.

        Arguments:
          node:Node -- Node to which the NIU is attached.
          devicename:String -- Name to access the NIU on the node.
        Return value: None.
        """
        self._node = node
        self.devicename = devicename
        self.fullName = "%s.%s"%(node.hostname, devicename)

    def attachToMedium(self, medium, position):
        """Attach the NIU to a transmission medium.

        Call medium.attachNIU to inform it of its new NIU.

        Arguments:
          medium:Medium
          position:PositionType -- Coordinates of the NIU on the medium
        Return value: None."""

        self.medium = medium
        medium.attachNIU(self, position)

    def addProtocol(self, protocolEntity, protocolName):
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
        setattr(self, protocolName, protocolEntity)
        protocolEntity.install(self, protocolName)
