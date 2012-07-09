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

"""Implementation of transmission media like bus or point-to-point link."""

__all__ = ["Bus", "IdealRadioChannel", "PtPLink", "ErrorPtPLink", "ErrorRadioChannel"]

from random import randint, random, sample
from math import ceil,log,sqrt
import numpy
from netbase import Medium
from simulator import SCHEDULE


class Bus(Medium):
    """A bus physical transmission medium.

    The Bus class implements a bus transmission medium. Multiple NIUs can be
    attached to the bus. The position is a length coordinate in meters. The
    signals are propagated bidirectionally along the bus from the transmitter
    NIU to all connected NIUs. The propagation delay depends on the
    signalSpeed of the medium and on the distance of the receiver NIU from
    the transmitter NIU."""

    def __init__(self):
        self._niuDict = {}
        self.signalSpeed = 0.77*3e8

    def attachNIU(self, niu, position):
        """Attachs a NIU to the medium.

        Extends Medium.attachNIU by additionally checking that the position
        is a 1-dimensional coordinate (float).

        Arguments:
          niu:NIU -- NIU that attaches itself to the medium.
          position:float -- Coordinates of the NIU on the medium.
        Return value: None.
        """
        try:
            position = float(position)
        except TypeError:
            raise TypeError("Position of the NIU on a bus must be a float.")
        self._niuDict[niu] = position

    def startTransmission(self, txNIU):
        """Start a transmission on the medium.

        A phy protocol entity calls this method to indicate that it
        starts the transmission of a signal. All NIUs but the
        transmitting NIU are informed, after the propagation delay,
        that a new transmission has started by calling the method
        phy.newChannelActivity of their phy entities. No data is
        actually transmitted. This will be done by the function
        completeTransmission, which is called by the phy layer entity
        at the end of the transmission.

        Arguments:
          niu:NIU -- Transmitting NIU
        Return value: None.
        """
        txPos = self._niuDict[txNIU]
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = abs(rxPos - txPos)/self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.newChannelActivity)
        
    def completeTransmission(self, txNIU, data):
        """Finish a transmission and deliver the data to receiving NIUs.

        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        delivered, after a propagation delay, to the phy entities of
        attached NIUs by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """
        
        txPos = self._niuDict[txNIU]
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = abs(rxPos - txPos)/self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.receive, (data,))

class IdealRadioChannel(Bus):
    """Ideal radio channel without attenuation or bit errors.

    The only difference with respect to a bus is that node coordinates
    are two-dimensional.
    """
    
    def __init__(self):
        self._niuDict = {}
        self.signalSpeed = 3.0*3e8

    def attachNIU(self, niu, position):
        """Attachs a NIU to the medium.

        Extends Medium.attachNIU by additionally checking that the position
        is a 2-dimensional coordinate (float).

        Arguments:
          niu:NIU -- NIU that attaches itself to the medium.
          position:(float,float) -- Coordinates of the NIU on the medium.
        Return value: None.
        """
        message="Position of a NIU on a radio channel must be two-dimensional"
        try:
            if len(position) != 2:
                raise TypeError(message)
        except TypeError:
            raise TypeError(message)
        try:
            posx = float(position[0])
            posy = float(position[1])
        except TypeError:
            raise TypeError(message)
        self._niuDict[niu] = (posx,posy)
        
        self._distances = {}
        for niu1 in self._niuDict.keys():
            pos1 = self._niuDict[niu1]
            for niu2 in self._niuDict.keys():
                pos2 = self._niuDict[niu2]
                dist = sqrt( (pos1[0]-pos2[0])**2 + (pos1[1]-pos2[1])**2 )
                self._distances[(niu1,niu2)] = dist

    def startTransmission(self, txNIU):
        """Start a transmission on the medium.

        A phy protocol entity calls this method to indicate that it
        starts the transmission of a signal. All NIUs but the
        transmitting NIU are informed, after the propagation delay,
        that a new transmission has started by calling the method
        phy.newChannelActivity of their phy entities. No data is
        actually transmitted. This will be done by the function
        completeTransmission, which is called by the phy layer entity
        at the end of the transmission.

        Arguments:
          niu:NIU -- Transmitting NIU
        Return value: None.
        """
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = self._distances[(txNIU,rxNIU)] / self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.newChannelActivity)
        
    def completeTransmission(self, txNIU, data):
        """Finish a transmission and deliver the data to receiving NIUs.

        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        delivered, after a propagation delay, to the phy entities of
        attached NIUs by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = self._distances[(txNIU,rxNIU)] / self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.receive, (data,))


class PtPLink(Medium):
    """A point-to-point link physical transmission medium.

    Implements a point-to-point link transmission medium. Two NIUs can be
    attached to the link. The position is a length coordinate in meters. The
    signals are propagated from the transmitter NIU to the other NIUs.
    The propagation delay depends on the signalSpeed of the medium and on
    the distance of the two NIUs, i.e., the length of the link.
    It depends on the phy layer entities whether the link is full-duplex or
    half-duplex. When a transmission is started by one NIU, the other NIUs
    will be informed. It can then choose to ignore the channel activity
    (in full-duplex mode) or to take it into account for its own
    transmissions (half-duplex).
    """

    def __init__(self):
        self._niuDict = {}
        self.signalSpeed = 0.77*3e8

    def attachNIU(self, niu, position):
        """Attachs a NIU to the medium.

        Extends Medium.attachNIU by additionally checking that the position
        is a 1-dimensional coordinate (float) and that only two NIUs are
        attached.

        Arguments:
          niu:NIU -- NIU that attaches itself to the medium.
          position:float -- Coordinates of the NIU on the medium.
        Return value: None.
        """
        try:
            position = float(position)
        except TypeError:
            raise TypeError("Position of the NIU on a bus must be a float.")
        if len(self._niuDict.items()) > 1:
            raise IndexError("At most two NIUs can be attached to a "
                             "point-to-point link")
        self._niuDict[niu] = position

    def startTransmission(self, txNIU):
        """Start a transmission on the medium.

        A phy protocol entity calls this method to indicate that it
        starts the transmission of a signal. The other NIU is
        informed, after the propagation delay, that a new transmission
        has started by calling the method phy.newChannelActivity of
        its phy entity. No data is actually transmitted. This will be
        done by the function completeTransmission, which is called by
        the phy layer entity at the end of the transmission.

        Arguments:
          niu:NIU -- Transmitting NIU
        Return value: None.
        """
        txPos = self._niuDict[txNIU]
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = abs(rxPos - txPos)/self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.newChannelActivity)
        
    def completeTransmission(self, txNIU, data):
        """Finish a transmission and deliver the data to the receiving NIU.

        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        delivered, after a propagation delay, to the phy entity of
        the other attached NIU by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """
        
        txPos = self._niuDict[txNIU]
        for rxNIU, rxPos in self._niuDict.items():
            if rxNIU != txNIU:
                propDelay = abs(rxPos - txPos)/self.signalSpeed
                SCHEDULE(propDelay, rxNIU.phy.receive, (data,))


class ErrorMedium(Medium):
    """Abstract base class for a medium that simulates transmission errors.

    Implemented error models are:
      - 'bernoulli': Independent bit errors with a error probability BER
                     This is the default, but with BER=0.0
      - 'uniform': All number of bit errors are equally likely.
    Some methods of this class are virtual, i.e. it cannot be instantiated.
    """

    errorbits = None
    """Function that returns a list of indices of the bits to modify."""

    def __init__(self):
        self.errorbits = self._bernoulliErrors
        self.BER = 0.0

    def errorModel(self,model='bernoulli',*args):
        """Sets the error model of the medium.

        The model may be:
          - 'bernoulli': Independent bit errors are simulated.
                         One additional argument gives the bit error rate.
                         This is the default.
          - 'uniform': The number of bit errors in a frame is uniformly
                       distributed between n1 and n2 errors (inclusive).
                       Two additional parameters provide the values of n1 and
                       n2. For example, if n1=0 and n2=9, 0 to 9 bit errors
                       may occur in each frame, each with a probability of 0.1
        """
        if model == 'bernoulli':
            assert len(args)==1
            self.BER = args[0]
            self._errorbits = self._bernoulliErrors
        elif model == 'uniform':
            if args:
                assert len(args)==2
                self.minbits, self.maxbits = args
            else:
                self.minbits=0; self.maxbits=10e300
            self._errorbits = self._uniformErrors
        else:
            raise ValueError("Unknown error model: "+model)

    def corrupt(self,data):
        """Introduce bit errors into the data.

        A very simple model with independent bernoulli errors is used.
        This does not reflect the behavior of realistic channels where bit
        errors are correlated.
        """
        errorbits = self._errorbits(data)
        dataarray = numpy.fromstring(data,numpy.UnsignedInt8)
        bitmask = (128,64,32,16,8,4,2,1)
        for pos in errorbits:
            byte = pos>>3 # Divide by 8
            bit = pos & 7 # mod 8. This is twice faster than divmod
            dataarray[byte] = dataarray[byte] ^ bitmask[bit]
        data = dataarray.tostring()
        return data
                
    def _bernoulliErrors(self,data):
        """Simulate independent bit errors with a given probability.
        This model is not very realistic, since it cannot model the
        correlation of bursts of bits.
        """
        errorbits = []
        if self.BER:
            # The distance between bit errors has a geometric distribution.
            length=len(data)*8
            pos = self._geomvariate(self.BER)
            while pos < length:
                errorbits.append(pos)
                pos += self._geomvariate(self.BER)
        return errorbits

    def _uniformErrors(self,data):
        """Simulate errors where the number of bit errors has a uniform dist.
        """
        n = len(data)*8
        minbits = self.minbits
        maxbits = min(self.maxbits,n)
        return sample(xrange(n),randint(minbits,maxbits))

    def _geomvariate(self, p):
        """Return a geometrically distr. random number for the probability p.

        The algorithms is from Knuth, 'The Art of Computer Programming', Vol.2,
        p. 136, 3rd edition, Addison-Wesley, 1997.
        """
        return int(ceil(log(random())/log(1-p)))


class ErrorPtPLink(ErrorMedium, PtPLink):
    """Point to point link that simulates bit errors in transmissions."""

    def __init__(self):
        ErrorMedium.__init__(self)
        PtPLink.__init__(self)

    def completeTransmission(self,txNIU,data):
        """Introduce bit errors and deliver the data to the receiving NIU.

        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        first corrupted according to the error model and then delivered,
        after a propagation delay, to the phy entity of the other attached
        NIU by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """
        data = self.corrupt(data)
        super(ErrorPtPLink,self).completeTransmission(txNIU,data)


class ErrorBus(ErrorMedium, Bus):
    """Bus that simulates bit errors in transmissions."""

    def __init__(self):
        ErrorMedium.__init__(self)
        Bus.__init__(self)

    def completeTransmission(self,txNIU,data):
        """Introduce bit errors and deliver the data to the receiving NIU.

        All receiving NIUs get identical frames, i.e, with the same errors.
        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        first corrupted according to the error model and then delivered,
        after a propagation delay, to the phy entity of the other attached
        NIUs by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """

        data = self.corrupt(data)
        super(ErrorBus,self).completeTransmission(txNIU,data)
        
        
        
class ErrorRadioChannel(ErrorMedium, IdealRadioChannel):
    """Radio Channel that simulates bit errors in transmissions."""
    
    def __init__(self):
        ErrorMedium.__init__(self)
        IdealRadioChannel.__init__(self)
        
    def completeTransmission(self,txNIU,data):
        """Introduce bit errors and deliver the data to the receiving NIU.

        All receiving NIUs get identical frames, i.e, with the same errors.
        By calling this method, a phy layer entity of an attached NIU
        indicates that it has finished the transmission previously started
        by calling startTransmission. The data provided to the medium is
        first corrupted according to the error model and then delivered,
        after a propagation delay, to the phy entity of the other attached
        NIUs by calling phy.receive.

        Arguments:
          txNIU:NIU -- Transmitting NIU
          data:Bitstream -- Transmitted data
        Return value: None.
        """

        data = self.corrupt(data)
        super(ErrorRadioChannel,self).completeTransmission(txNIU,data)




if __name__ == "__main__":

    cable = ErrorPtPLink()
    
    data = 'A beautiful ASCII string in input'
    
    print "***Control Procedure : Bits Error***"
    
    print "1. Bernoulli model"

    BER = 0.01
    cable.errorModel('bernoulli', BER)
    data_error = cable.corrupt(data)
    print "   Data input:  ", data
    print "   Data output: ", data_error


    print "2. Uniform model"
    minbits=0
    maxbits=4
    cable.errorModel('uniform', minbits, maxbits)
    data_error = cable.corrupt(data)
    print "   Data input:  ", data
    print "   Data output: ", data_error
    
    data_error = cable.errorbits(data)
    print "   Data output: ", data_error













