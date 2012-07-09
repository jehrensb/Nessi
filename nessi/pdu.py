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

"""Factory functions and base classes for PDUs.

A Protocol Data Unit defined the format and contains the data of packets
exchanged between protocols. This module defines a base class for PDUs
from which all other PDU types are inherited. The users does not have to
program new PDU types, e.g., for Ethernet, Token Ring, IP, ... The module
provides a factory function 'formatFactory' that create a new class (not
an object, a new class) from a format description. The new class can
then be used to instantiate PDU objects of this format, e.g., Ethernet frames.
"""

__all__ = ["PDUFormatError", "PDU", "formatFactory"]

import copy
import struct


class PDUFormatError(Exception):
    """Exception for errors in PDU formats."""
    pass


class PDU(object):
    """Base class for packet data units.

    All new PDU classes, as created by the formatFactory, are inherited
    from this class. 
    The class object provides two methods:
      - serialize -- Creates a bitstream of the content of the data that
                     can be transfered to lower protocol layers or across
                     the network.
      - fill -- Take a received bitstream and fill the pdu field with its
                content. The pdu fields can then be read.

    A protocol developer should not program new PDU classes manually. Instead
    he should use the formatFactory function that generates a new class from
    a format description.
    """

    def serialize(self):
        """Return a Bitstream of the PDU content.

        The Bitstream can then be transmitted over a physical medium.

        Return value: Bitstream.

        """
        return self._data[:-1]
        
    def fill(self, bitstream):
        """Parse the bitstream and set the value of all PDU fields.

        The fields can then be accessed as attributes of the PDU, e.g.,
        PDU.checksum for the field named 'checksum'

        Argument:
          bitstream:Bitstream -- Sequence of bits received from lower layer.
        Return value: None.
        """

        self._data = bitstream+"\x00"


def _propertyFactory(type, start, end, length):
    """Create a property with a get and a set method for a PDU field.

    This function is called by the formatFactory to create a property
    of a new PDU class. This property can then be added to the new
    PDU class to allow reading and writing of PDU fields.

    Example: if the new PDU class EthernetPDU has a field 'FCS' of type 'Int',
    then this function creates a property object p with two functions to
    get and set this field. The caller can add this property to the new
    class like EthernetPDU.FCS = p. Each object instantiated from this
    class will then have an attribute FCS that allows reading and
    writing of the field.

    Arguments:
      type:FieldType -- Type of the field, like ('ByteField', 'BitField',
                                                 'MACAddr', 'IPv4Addr', 'Int')
      start:Int -- Position of the first bit of the field in the packet.
                   Attention: may be negative, to count from the back
      end:Int -- Position of the first bit of the next field.
                 The last field of the packet is always a hidden sentinel of
                 one octet, such that end always has a defined value.
                 Attention: may be negative to count from the back.
      length:Int -- Length of the field in bits.
    Return value: A property to that can be added to a class.
      """
    
    if type == 'ByteField':
        start /= 8
        end /= 8

        def getfield(self):
            return self._data[start:end]

        def setfield(self, value):
            self._data = self._data[:start]+value+self._data[end:]

    elif type == 'Int':
        start /= 8
        length /= 8
        end /= 8
        pad = "\x00"*8
        def getfield(self):
            octets = self._data[start:end]
            return struct.unpack("!q", pad[0:-length]+octets)[0]

        def setfield(self, value):
            if value >= 1L<<(length*8):
                raise ValueError("Value "+ `value`+ " too large for IntField of "
                                 + `length` + " octets")
            
            octets = struct.pack("!q", value)[-length:]
            self._data = self._data[:start]+octets+self._data[end:]
            
    elif type == "IPv4Addr":
        start /= 8
        length /= 8
        end /= 8
        
        def getfield(self):
            octets = self._data[start:end]
            ints = struct.unpack("!BBBB", octets)
            return "%d.%d.%d.%d"%ints
        
        def setfield(self, value):
            ints = [int(s) for s in value.split('.')]
            args = ["!BBBB"]+ints
            octets = struct.pack(*args)
            self._data = self._data[:start]+octets+self._data[end:]

    elif type == 'MACAddr':
        start /= 8
        length /= 8
        end /= 8
        
        def getfield(self):
            octets = self._data[start:end]
            ints = struct.unpack("!BBBBBB", octets)
            return "%02X:%02X:%02X:%02X:%02X:%02X"%ints

        def setfield(self, value):
            value = long(value.replace(":", ""),16)
            octets = struct.pack("!Q", value)[-length:]
            self._data = self._data[:start]+octets+self._data[end:]

    elif type == 'BitField':
        firstOctet, offset = divmod(start,8)
        lastOctet = (end-1) / 8
        trailbits = (8 - (end % 8)) % 8
        if firstOctet == lastOctet:
            # Bitfield in a single octet. Use fast and simple functions
            mask = ((1<<length)-1)<<trailbits
            invmask = ~mask
            def getfield(self):
                octet = self._data[firstOctet]
                return (ord(octet) & mask)>>trailbits
            def setfield(self, value):
                if value >= (1<<length):
                    raise ValueError("Value "+ `value`
                                     + " too large for BitField of "
                                     + `length` + " bits")
                value <<= trailbits
                octet = self._data[firstOctet]                
                octet = chr(ord(octet) & invmask | value)
                self._data = (self._data[:firstOctet] + octet 
                              + self._data[firstOctet+1:])
        else:
            # Bitfield crosses octet boundary. Use more complex functions
            startmask = (1<<(8-offset))-1
            endmask = ~((1<<trailbits)-1)
            def getfield(self):
                value = 0
                octets = self._data[firstOctet:lastOctet+1]
                value = ord(octets[0]) & startmask
                for octet in octets[1:-1]:
                    value = value * 256 + ord(octet)
                value = (value * (1<<(8-trailbits)) 
                         + ((ord(octets[-1]) & endmask)>>trailbits))
                return value
            def setfield(self, value):
                if value >= (1L<<length):
                    raise ValueError("Value "+ `value`
                                     + " too large for BitField of "
                                     + `length` + " bits")
                value, rem = divmod(value,1<<(8-trailbits))
                octet = self._data[lastOctet]
                newData = chr(ord(octet) & (~endmask) | (rem<<trailbits))
                for i in range(firstOctet+1,lastOctet):
                    value, rem = divmod(value, 256)
                    newData = chr(rem)+newData
                octet = self._data[firstOctet]
                newData = chr(ord(octet) & (~startmask) | value) + newData
                self._data = (self._data[:firstOctet] + newData 
                              + self._data[lastOctet+1:])
                
    return property(getfield, setfield, None, "")


def _initFactory(defaultdata):
    """Return an init function of the new class that sets default values."""
    def init(self):
        self._data = defaultdata
    return init


def _classFactory(_slots,_format,_protocolEntity):
    """Return a new class for a PDU type."""
    class newFormat(PDU):
        __slots__ = _slots+('_data',)
        format = _format
        protocolEntity = _protocolEntity
        """Protocol entity that used the PDU. Used for packet tracing."""
    return newFormat


def _checkformat(format):
    """Verify that the format, that defines a new PDU class, is correct."""
    variableLen = 0
    start,end = 0,0
    for name, type, length, default in format:
        if length == None:
            if type != "ByteField":
                raise PDUFormatError("Only ByteField can have an unspecified "+
                                     "length")
            variableLen += 1
            length = 0
        end += length
        if type not in ("ByteField", "BitField", "MACAddr", "IPv4Addr", "Int"):
            raise PDUFormatError("Unknown PDU field type: " + type)

        if type == 'ByteField':
            if not (start%8 == end%8 == 0):
                raise PDUFormatError("ByteField must be aligned on octet boundary")
            
        elif type == 'MACAddr':
            if length != 48:
                raise PDUFormatError("MACAddr field must be 48 bits long")
            if start%8 != 0:
                raise PDUFormatError("MACAddr must be aligned on octet boundary")                
        elif type == 'IPv4Addr':
            if length != 32:
                raise PDUFormatError("IPv4Addr field must be 32 bits long")
            if start%8 != 0:
                raise PDUFormatError("IPv4Addr must be aligned on octet boundary")                
        elif type == 'Int':
            if length > 64:
                raise PDUFormatError("Int field can be at most 64 bits long")
            if not (start%8 == length%8 == 0):
                raise PDUFormatError("Int PDU Field must be aligned on octet boundary")
        elif type == 'BitField':
            startoctet = start % 8
            endoctet = (end+7) % 8
            if endoctet - startoctet > 8:
                raise PDUFormatError("BitField too long. Does not fit into 8 octet-aligned bytes") 
        start += length
    if variableLen > 1:
        raise PDUFormatError("Multiple variable length fields in PDU format")


def formatFactory(format, protocolEntity):
    """Create a new class (not an object, but a class) for a PDU type.

    This function takes a format description of a packet type and
    returns a new class that can be used to create pdu objects.
    A PDU is defined by a packet format that has the following
    structure: list of tuples: (name, type, length, default).
    Name is the name of the packet field, e.g., destAddr.
    Type is a string out of
      - 'ByteField' -- Arbitrary sequence of octets. Value: string as 'abcd'
      - 'BitField' -- Sequence of bits. Value: integer as int('101',2).
      - 'MACAddr' -- MAC address. Value: string as '20:C0:83:AD:33:01'
      - 'IPv4Addr' -- IPv4 address. Value: string as '192.168.10.01'
      - 'Int' -- Integer of arbitrary length. Value: integer as 123456

    The parameter length specifed the length of the field, in bits.
    ByteField fields may have an arbitrary length, like data fields, whose
    length is not known in advance. In this case, a length = None is specified.
    There may only be one such field in a format and it must be a ByteField.
    BitField fields may have an arbitrary length, like 1 or 3.
    MACAddr fields must have the length 48.
    IPv4Addr fields must have the length 32.
    Int fields must have a length that is a multiple of octets.
    All fields but BitField must be octet aligned, which means that they
    must start and end at octet boundaries.

    The parameter default specifes the default value of a field when
    a new PDU object is created. A value None means no default value.

    The format of an Ethernet-II frame can be defined as follows:
      [('preamble', 'Int', 64, int('10101010'*7+'10101011',2)),
       ('destAddr', 'MACAddr', 48, 'FF:FF:FF:FF:FF:FF'),
       ('srcAddr',  'MACAddr', 48, None),
       ('type', 'Int', 16, 0x800),
       ('data', 'ByteField', None, None),
       ('FCS', 'Int', 32, None)]

    When an pdu object is instantiated from a PDU class created by this
    function, the packet fields can be accessed (get and set) as attributes
    of the objects, e.g., pdu.srcAddr = '12:43:EE:C0:2A:01'.
    The new class object provides two more methods that are inherited from the
    base class PDU:
      - serialize -- Creates a bitstream of the content of the data.
      - fill -- Take a received bitstream and fill the pdu field with it.

    A protocol developer should not program new PDU classes manually. Instead
    he should use this function to dynamically generate a new class from
    a format description.

    Arguments:
      format:PDUFormat -- Description of the packet fields as given above.
      protocolEntity -- Protocol entity to which the PDU belongs
    Return value: A new PDU class.
    """

    _checkformat(format)
    
    # Create the new class
    slots = tuple([name for name, type, length, default in format])
    newFormat = _classFactory(slots, format, protocolEntity)

    # Determine the start and end indices of fields, taking into account
    # variable length fields
    formatcopy = copy.copy(format)
    start1 = []
    pos = 0
    for name, type, length, default in format:
        del formatcopy[0]
        start1.append(pos)
        if length == None:
            break
        else:
            pos += length
    totalLength = pos
    
    start2 = [-8] # Last octet of data is a sentinel
    pos = -8
    formatcopy.reverse()
    for name, type, length, default in formatcopy:
        pos -= length
        start2.append(pos)
    totalLength -= pos
    start2.reverse()
    start=start1+start2

    totalLength,rem = divmod(totalLength,8)
    if rem != 0:
        raise PDUFormatError("Total PDU length must be a multiple of 8 bits")
    newFormat.__init__ = _initFactory("\x00"*totalLength)

    # Create the property functions to access the PDU fields
    pos = 0
    for name, type, length, default in format:
        p = _propertyFactory(type, start[pos], start[pos+1], length)
        setattr(newFormat, name, p)
        pos += 1

    pdu = newFormat()
    for name, type, length, default in format:
        if default != None:
            setattr(pdu, name, default)
    newFormat.__init__ = _initFactory(pdu.serialize()+"\x00")    

    return newFormat

###########################################################################
# Module check code. Is executed when the file is executed as script and
# not loaded as module.

if __name__ == '__main__':
    # Create formats that test each field type at the head and
    # at the end of a PDU, both with and without a variable length field
    # in the PDU.

    format = [("By1", "ByteField", 80, "2224567890"),
              ("M1", "MACAddr", 48, None),
              ("IP1", "IPv4Addr", 32, None),
              ("Shortbit1","BitField", 3, int("111",2)),
              ("Shortbit2","BitField", 1, None),
              ("Longbit1","BitField", 6, None),
              ("Longbit2","BitField", 19, None),
              ("Shortbit3","BitField", 3, None),
              ("In1", "Int", 32, 334),
              ("data", "ByteField", None, "sdfasdfasdfas"),
              ("By2", "ByteField", 80, None),
              ("M2", "MACAddr", 48, "AA:00:30:11:FF:01"),
              ("IP2", "IPv4Addr", 32, "255.255.255.128"),
              ("Shortbit4","BitField", 3, None),
              ("Shortbit5","BitField", 1, None),
              ("Longbit3","BitField", 6, None),
              ("Longbit4","BitField", 19, None),
              ("Shortbit6","BitField", 3, None),
              ("In2", "Int", 32, 1)]

    PDUClass = formatFactory(format,None)
    pdu1 = PDUClass()
    pdu2 = PDUClass()
    try:
        pdu1.sdfasd = 0 
        assert("Slots do not work")
    except AttributeError:
        pass

    assert(pdu1.By1 == "2224567890")
    assert(pdu1.Shortbit1 == int("111",2))
    assert(pdu1.data == "sdfasdfasdfas")
    assert(pdu1.M2 == "AA:00:30:11:FF:01")
    assert(pdu1.IP2 == "255.255.255.128")
    assert(pdu1.In2 == 1)

    pdu1.By1 = "1234567890"
    pdu1.M1 = "12:34:56:78:9A:BC"
    pdu1.IP1 = "120.0.23.255"
    pdu1.Shortbit1 = int("101",2)
    pdu1.Shortbit2 = int("0",2)
    pdu1.Longbit1 = int("101011",2)
    pdu1.Longbit2 = int("1001110100110100110",2)
    pdu1.Shortbit3 = int("110",2)
    pdu1.In1 = 321232233
    pdu1.data = "abcdefg"
    pdu1.By2 = "1234567890"
    pdu1.M2 = "12:34:56:78:9A:BC"
    pdu1.IP2 = "120.0.23.255"
    pdu1.Shortbit4 = int("101",2)
    pdu1.Shortbit5 = int("0",2)
    pdu1.Longbit3 = int("101011",2)
    pdu1.Longbit4 = int("1001110100110100110",2)
    pdu1.Shortbit6 = int("110",2)
    pdu1.In2 = 321232233

    assert(pdu1.By1 == "1234567890")
    assert(pdu1.M1 == "12:34:56:78:9A:BC")
    assert(pdu1.IP1 == "120.0.23.255")
    assert(pdu1.Shortbit1 == int("101",2))
    assert(pdu1.Shortbit2 == int("0",2))
    assert(pdu1.Longbit1 == int("101011",2))
    assert(pdu1.Longbit2 == int("1001110100110100110",2))
    assert(pdu1.Shortbit3 == int("110",2))
    assert(pdu1.In1 == 321232233)
    assert(pdu1.data == "abcdefg")
    assert(pdu1.By2 == "1234567890")
    assert(pdu1.M2 == "12:34:56:78:9A:BC")
    assert(pdu1.IP2 == "120.0.23.255")
    assert(pdu1.Shortbit4 == int("101",2))
    assert(pdu1.Shortbit5 == int("0",2))
    assert(pdu1.Longbit3 == int("101011",2))
    assert(pdu1.Longbit4 == int("1001110100110100110",2))
    assert(pdu1.Shortbit6 == int("110",2))
    assert(pdu1.In2 == 321232233)

    # Change the length of the variable field and test again
    pdu1.data = "sdfasdfasdfasdfas"
    assert(pdu1.By1 == "1234567890")
    assert(pdu1.M1 == "12:34:56:78:9A:BC")
    assert(pdu1.IP1 == "120.0.23.255")
    assert(pdu1.Shortbit1 == int("101",2))
    assert(pdu1.Shortbit2 == int("0",2))
    assert(pdu1.Longbit1 == int("101011",2))
    assert(pdu1.Longbit2 == int("1001110100110100110",2))
    assert(pdu1.Shortbit3 == int("110",2))
    assert(pdu1.In1 == 321232233)
    assert(pdu1.data == "sdfasdfasdfasdfas")
    assert(pdu1.By2 == "1234567890")
    assert(pdu1.M2 == "12:34:56:78:9A:BC")
    assert(pdu1.IP2 == "120.0.23.255")
    assert(pdu1.Shortbit4 == int("101",2))
    assert(pdu1.Shortbit5 == int("0",2))
    assert(pdu1.Longbit3 == int("101011",2))
    assert(pdu1.Longbit4 == int("1001110100110100110",2))
    assert(pdu1.Shortbit6 == int("110",2))
    assert(pdu1.In2 == 321232233)

    # Change all fields to another value and test again
    pdu1.By1 = "9876543210"
    pdu1.M1 = "00:FF:10:97:9A:BC"
    pdu1.IP1 = "0.10.23.101"
    pdu1.Shortbit1 = int("001",2)
    pdu1.Shortbit2 = int("1",2)
    pdu1.Longbit1 = int("101001",2)
    pdu1.Longbit2 = int("0100101010101010001",2)
    pdu1.Shortbit3 = int("101",2)
    pdu1.In1 = 34234
    pdu1.data = "ab"
    pdu1.By2 = "9876543210"
    pdu1.M2 = "00:FF:10:97:9A:BC"
    pdu1.IP2 = "0.10.23.101"
    pdu1.Shortbit4 = int("10",2)
    pdu1.Shortbit5 = int("1",2)
    pdu1.Longbit3 = int("110010",2)
    pdu1.Longbit4 = int("0010101011110011111",2)
    pdu1.Shortbit6 = int("011",2)
    pdu1.In2 = 23231231

    assert(pdu1.By1 == "9876543210")
    assert(pdu1.M1 == "00:FF:10:97:9A:BC")
    assert(pdu1.IP1 == "0.10.23.101")
    assert(pdu1.Shortbit1 == int("001",2))
    assert(pdu1.Shortbit2 == int("1",2))
    assert(pdu1.Longbit1 == int("101001",2))
    assert(pdu1.Longbit2 == int("0100101010101010001",2))
    assert(pdu1.Shortbit3 == int("101",2))
    assert(pdu1.In1 == 34234)
    assert(pdu1.data == "ab")
    assert(pdu1.By2 == "9876543210")
    assert(pdu1.M2 == "00:FF:10:97:9A:BC")
    assert(pdu1.IP2 == "0.10.23.101")
    assert(pdu1.Shortbit4 == int("10",2))
    assert(pdu1.Shortbit5 == int("1",2))
    assert(pdu1.Longbit3 == int("110010",2))
    assert(pdu1.Longbit4 == int("0010101011110011111",2))
    assert(pdu1.Shortbit6 == int("011",2))
    assert(pdu1.In2 == 23231231)

    pdu2.fill(pdu1.serialize())
    assert(pdu2.By1 == "9876543210")
    assert(pdu2.M1 == "00:FF:10:97:9A:BC")
    assert(pdu2.IP1 == "0.10.23.101")
    assert(pdu2.Shortbit1 == int("001",2))
    assert(pdu2.Shortbit2 == int("1",2))
    assert(pdu2.Longbit1 == int("101001",2))
    assert(pdu2.Longbit2 == int("0100101010101010001",2))
    assert(pdu2.Shortbit3 == int("101",2))
    assert(pdu2.In1 == 34234)
    assert(pdu2.data == "ab")
    assert(pdu2.By2 == "9876543210")
    assert(pdu2.M2 == "00:FF:10:97:9A:BC")
    assert(pdu2.IP2 == "0.10.23.101")
    assert(pdu2.Shortbit4 == int("10",2))
    assert(pdu2.Shortbit5 == int("1",2))
    assert(pdu2.Longbit3 == int("110010",2))
    assert(pdu2.Longbit4 == int("0010101011110011111",2))
    assert(pdu2.Shortbit6 == int("011",2))
    assert(pdu2.In2 == 23231231)
    
    print "All tests passed"
