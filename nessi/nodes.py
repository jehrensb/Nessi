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
Implementations of different node types, e.g. hosts, routers, ...
"""

__all__ = ["Host"]

from netbase import Node


class Host(Node):
    """Implementation of a terminal system."""
    
    def __init__(self):
        """Initialize the hostname and the device list."""
        self.hostname = 'localhost'
        self.devices = []

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
        self.devices.append(dev)
        setattr(self, devname, dev)
        dev.setNode(self, devname)

    def addProtocol(self, protocolEntity, protoName):
        """Add a new protocol entity to the node under the given name.

        After adding, the protocol entity is accessible as a public data
        member of the node with the protoName as attribute name.
        The method calls protocolEntity.install to give the protocol
        the possibility to initialize itself.
        If the protocolEntity is a network layer protcol, it should add
        itself to the nwProtocols dictionary with its protocol number.

        Arguments:
          protocolEntity : ProtocolEntity
          protoName : String
        Return value : None.
        """
        setattr(self, protoName, protocolEntity)
        protocolEntity.install(self, protoName)

