# Nessi Network Simulator
#
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: October 2003
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

"""Implementation of different checksum algorithm and Traffic sources and sinks."""
__all__=["ChksumSource", "ChksumSink",
         "IPChksum", "checkIPChksum",
         "polynomialChksum", "checkPolynomialChksum",
         "parityChksum", "checkParityChksum",
         "doubleParityChksum", "checkDoubleParityChksum"]

import array
import numpy
import struct
from math import ceil
from simulator import SCHEDULE
from trafficgen import TrafficSource, TrafficSink

#-----------------------------------------------------------------------------

class ChksumSource(TrafficSource):
    """Sends a fixed sized packet to lower layers at periodic intervals."""

    chksumFun = None # Function to compute the checksum of a packet

    def __init__(self, interval=0.001, length=128):
        self.interval = interval
        self.length = length/8 # in octets
        self._lowerLayers = []

    def setParameters(self, interval, length):
        self.interval = interval
        self.length = length/8 # in octets

    def registerLowerLayer(self, lowerLayer):
        """Connect to a lower layer entity to send packets.

        PDUs can then be sent using the lowerLayerEntity send method.
        Several lower layers may be registered. The same packet will be
        sent to all of them
        """
        self._lowerLayers.append(lowerLayer)

    def useChksum(self,chksumFun):
        """Set the function that computes the checksum of a data packet.

        The checksum is a function that accepts a data packet and returns
        the checksum of the data as a string.
        """
        self.checksum = chksumFun

    def start(self):
        SCHEDULE(self.interval, self.generate)

    def generate(self):
        data = 'y'*self.length # A string 'xxxxx' of the correct length
        packet = data + self.checksum(data)
        self.send(packet)
        SCHEDULE(self.interval, self.generate)

    def send(self, packet):
        for lowerLayer in self._lowerLayers:
            lowerLayer.send(packet[:]) # Make a copy of the packet

#-----------------------------------------------------------------------------

class ChksumSink(TrafficSink):
    """Receive the same packet twice: once correctly and once with error.

    Compare the two packets and update statistics on the bit errors.
    """

    goodData = None # Holds the correct packet
    badData = None # Holds the packet with bit errors
    verifyChksumFun = None # Function to verify the checksum of a packet

    bitmasks = numpy.array([128,64,32,16,8,4,2,1],'b')

    def __init__(self):
        # Initialize the statistics
        # Dictionary: Error burst length --> How often detected
        self.burstsDetected = {}

        # Dictionary: Error burst length --> How often undetected
        self.burstsUndetected = {}

        # Dictionary: Number of wrong bits in packet --> How often detected
        self.bitErrorsDetected = {}

        # Dictionary: Number of wrong bits in packet --> How often undetected
        self.bitErrorsUndetected = {}

    def useChksum(self,verifyChksumFun):
        """Set the function to verify the checksum of a packet.

        The verifyChksumFun is a function that accepts a data packet with
        the a checksum and returns a tuple (data,correct), where data is
        the content of the packet without the checksum and correct is True if
        the checksum of the packet is correct.
        """
        self.verifyChksumFun = verifyChksumFun

    def receive(self,data):
        if not self.goodData: # This is the first of the two packets.Store it
            self.goodData = data
            return

        # We have the two packets. First check if an error is detected
        self.badData = data
        data , correct = self.verifyChksumFun(data)

        # Convert the strings into array of unsigned 8 bit integers
        # and compute the XOR between the arrays to find the bytes that differ
        goodbytes=numpy.fromstring(self.goodData,numpy.uint8)
        badbytes=numpy.fromstring(self.badData,numpy.uint8)
        diff = numpy.bitwise_xor(goodbytes,badbytes)

        # Convert the diff bytes into an array of bits,
        # e.g. [0,3,2] is converted to [00000000 00000011 00000010]
        diffbits = numpy.bitwise_and.outer(diff,self.bitmasks).flat

        # Get the indices of all error bits
        errorbits = numpy.nonzero(diffbits)[0]

        # Compute the statistics
        numErrors = len(errorbits)
        if numErrors:
            burstlength = max(errorbits)-min(errorbits)+1
            if correct:
                # Undetected bit errors !!!
                self.bitErrorsUndetected[numErrors] = (
                    self.bitErrorsUndetected.get(numErrors,0)+1)
                self.burstsUndetected[burstlength] = (
                    self.burstsUndetected.get(burstlength,0)+1)
            else:
                # Errors have been detected
                self.bitErrorsDetected[numErrors] = (
                    self.bitErrorsDetected.get(numErrors,0)+1)
                self.burstsDetected[burstlength] = (
                    self.burstsDetected.get(burstlength,0)+1)

        self.goodData = self.badData = None

# ---------------------------------------------------------------------------

def IPChksum(data):
    """Computes the IP checksum of the data and return it as a 2 byte string.

    According to RFC791:
    The checksum field is the 16 bit one's complement of the one's
    complement sum of all 16 bit words in the header.  For purposes of
    computing the checksum, the value of the checksum field is zero.

    This algorithm is quite stupid on modern machines since it forces us to
    do 16-bit one's complement arithmetic on 32-bit two's complement machines.
    """

    # First, convert every 2 octets into a short using big-endian byte order
    numWords = len(data)/2
    words = array.array("H") # Array of unsigned short integers (16 bit)
    words.fromstring(data) # Create a list of unsigned 16-bit integers
    words.byteswap() # Use big-endian order instead of little-endian
    words.append(0) # Add a word=0 for the empty checksum field

    # Algorithm according to:
    # http://www-mice.cs.ucl.ac.uk/multimedia/misc/tcp_ip/8804.mm.www/0252.html
    chksum = sum(words)
    firstword = chksum >> 16 # Take the upper 16 bits
    secondword = chksum & (2**16-1) # Take the lower 16 bits
    chksum = firstword+secondword
    chksum = ~chksum # One's complement, i.e. invert all bits
    chksum &= (2**16-1) # Only take lower 16 bits

    # What remains is to convert the chksum into two characters that
    # can be added to the packet
    chksumstring = chr(chksum>>8)+chr(chksum & (2**8-1))
    return chksumstring

def checkIPChksum(packet):
    """Check if the packet has a correct IP checksum.

    Returns a tuple:
      data: Content of the packet without the checksum
      correct: True, if no error has been detected, otherwise false.
    """
    data = packet[:-2]
    origChksum = packet[-2:]
    correct = ( IPChksum(data)==origChksum )
    return (data,correct)

# ---------------------------------------------------------------------------

def polynomialChksum(data,polynomial=[1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,1,
                                      0,0,0,1,1,1,0,1,1,0,1,1,0,1,1,1]):
    """Compute a polynomial checksum with the given generating polynomial.

    Arguments:
      data:String -- data to compute the checksum for
      polynomial:Sequence -- Binary coefficients of the generating polynomial.
                             Highest coefficient first,eg x**3+x**2=[1,1,0,0]
                             Default is the polynomial for CRC-32.
    Return value:
      checksum:String -- String of 4 octets of the checksum, highest bit first.
    """

    bitmask = numpy.array([128,64,32,16,8,4,2,1])
    bytes=numpy.fromstring(data,numpy.uint8)
    bits=numpy.bitwise_and.outer(bytes,bitmask).flat
    numpy.putmask(bits,bits,1)
    u=list(bits)+([0]*(len(polynomial)-1))
    u.reverse()
    v=polynomial[:]
    v.reverse()
    q,r = dividePolynomial(u,v)
    r = numpy.array(r)
    r = r[::-1] # Reverse it
    if len(r)%8:
        r=numpy.concatenate(([0]* (8 - len(r)%8), r))
    checksumstring=""
    for i in range(len(r)/8):
        checksumstring += chr(numpy.dot(r[i*8:(i+1)*8],bitmask))
    return checksumstring

def checkPolynomialChksum(packet,polynomial=[1,0,0,0,0,0,1,0,0,1,1,0,0,0,0,0,1,
                                             0,0,0,1,1,1,0,1,1,0,1,1,0,1,1,1]):
    """Check if the packet has a correct polynomial checksum.

    Arguments:
      packet:String -- packet with the checksum
      polynomial:Sequence -- Binary coefficients of the generating polynomial.
                             Highest coefficient first,eg x**3+x**2=[1,1,0,0]
                             Default is the polynomial for CRC-32.
    Returns a tuple:
      data: Content of the packet without the checksum
      correct: True, if no error has been detected, otherwise false.
    """
    chksumlen = int(ceil((len(polynomial)-1)/8.0))
    data = packet[:-chksumlen]
    origChksum = packet[-chksumlen:]
    correct = ( polynomialChksum(data,polynomial)==origChksum )
    return (data,correct)

def dividePolynomial(u,v):
    """Division of polynomial modulo 2

    This function returns two polynomials q and r such that
    u(x) = q(x).v(x) + r(x), deg(r) < dev(v).
    The coefficients of all polynomials are binary and the division
    is computed modulo 2.

    The algorithm is from Knuth, 'The Art of Computer Programming', Vol.2,
    p. 421, 3rd edition, Addison-Wesley, 1997.

    Arguments:
      u:Sequence -- Sequence of binary coefficients of the dividend
      v:Sequence -- Sequence of bin. coefficients of the divisor,deg(v)<=deg(u)
    Return value:
      q:Sequence -- Sequence of bin. coefficients or the result of the division
      r:Sequence -- Sequence of bin.coefficients or the result of the remainder
    All sequences are in reverse order, such that u[0] is the coefficient for
    x^0, etc.
    """
    assert v[-1]==1
    u2=u[:] # Make a copy to avoid modifying the original sequence
    m = len(u2)-1
    n = len(v)-1
    q=[0]*(m-n+1)
    klist = range(m-n+1)
    klist.reverse()
    for k in klist:
        q[k] = u2[n+k] & v[n]
        if not q[k]: continue
        jlist = range(k,n+k)
        for j in jlist:
            u2[j] = u2[j] ^ v[j-k]
    r = u2[0:n]

    while q and not q[-1]: del q[-1]
    return (q , r)

# ---------------------------------------------------------------------------

def parityChksum(data):
    """Computes the even parity bit and return it as a 1 byte string.

    Since we cannot return a single bit, the bit is encoded as an octet
    and the octet is taken as a character (e.g. character \x00 or \x01.
    """
    bitmask = numpy.array([128,64,32,16,8,4,2,1],numpy.uint8)
    bytes=numpy.fromstring(data,numpy.uint8)
    bits=numpy.bitwise_and.outer(bytes,bitmask).flat
    count = len(numpy.nonzero(bits))
    checksumstring = chr(count%2)
    return checksumstring

def checkParityChksum(packet):
    """Check if the packet has a correct even parity bit.

    Returns a tuple:
      data: Content of the packet without the checksum
      correct: True, if no error has been detected, otherwise false.
    """
    data = packet[:-1]
    # Pay attention to only use the last bit of the checksums
    origChksum = ord(packet[-1:]) & 1
    correct = ( ord(parityChksum(data)) & 1 == origChksum )
    return (data,correct)

# ---------------------------------------------------------------------------

def doubleParityChksum(data):
    """Computes horizontal an vertical parities.

    One horizontal parity bit is computed per octet. 8 vertical parity bits
    are computed. The checksum is the 8 vertical parity bits plus the
    horizontal parity bits, padded by a variable number of 0 bits to align
    on an octet boundary. Even parity is used.

    The checksum is returned as a string where each character codes a byte
    of the checksum.
    """
    bitmask = numpy.array([128,64,32,16,8,4,2,1])
    bytes = numpy.fromstring(data,numpy.uint8)
    numBytes = len(bytes)
    bits = numpy.bitwise_and.outer(bytes,bitmask).flat
    numpy.putmask(bits,bits,1)
    bits = numpy.reshape(bits, (numBytes,8))

    verParities = numpy.bitwise_and(numpy.sum(bits),1)
    bits = numpy.concatenate((bits,[verParities]))

    horParities = numpy.bitwise_and(numpy.sum(bits,1),1)
    if len(horParities)%8:
        horParities = numpy.concatenate((horParities,
                                           [0]*(8-len(horParities)%8)))

    bitmask = numpy.array([128,64,32,16,8,4,2,1])
    chksumstring = chr(numpy.dot(verParities,bitmask))
    for i in range(len(horParities)/8):
        chksumstring += chr(numpy.dot(horParities[i*8:(i+1)*8],bitmask))
    return chksumstring

def checkDoubleParityChksum(packet):
    """Check if the packet has correct horizontal and vertial parities.

    Returns a tuple:
      data: Content of the packet without the checksum
      correct: True, if no error has been detected, otherwise false.
    """
    packetlen = len(packet)
    datalen = (packetlen*8)/9 - 1 # Integer division. Equivalent to floor
    chksumlen = packetlen-datalen
    data = packet[:-chksumlen]
    origChksum = packet[-chksumlen:]
    # Clear the padding bits, since they should not be considered
    osum=0
    for byte in packet[-chksumlen:]:
        osum = osum*256 + ord(byte)
    osum &= (1<<(datalen+9))-1
    origChksum=""
    for i in range(chksumlen):
        osum,r=divmod(osum,256)
        origChksum = chr(r) + origChksum
    correct = ( doubleParityChksum(data)==origChksum )
    return (data,correct)


# Helper functions to test the checksum functions
def binary(z):
    """Returns a string with the binary representation of z.

    z can be an integer or a string.
    """
    r=""
    if type(z) == type(1) or type(z) == type(1L):
        while z!=0 and z !=-1:
            z,b=divmod(z,2)
            r = str(b)+r
        if z==-1:
            r = "(-)"+r
    elif type(z) == type("aaa"):
        bitmask=(128,64,32,16,8,4,2,1)
        for byte in z:
            B=ord(byte)
            for bit in bitmask:
                if B&bit:
                    r += "1"
                else:
                    r += "0"
    else:
        raise TypeError("Argument must be string or integer")
    return r

if __name__ == "__main__":
    print binary(polynomialChksum("\x00\x01"))
