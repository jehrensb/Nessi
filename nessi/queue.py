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

"""Implementation of packet quues with different scheduling disciplines."""

__all__ = ["Queue", "DropTail", "PrioQueue"]

from sys import maxint

class Queue(object):
    """Base class for queues"""

    def __init__(self):
        self._blocked = False
        """Indicated whether the queue waits for the end of a previous send."""
        self._rcvFun = None
        """Function to be called to send an element."""
        self._maxLen = maxint
        """Maximum queue length. May be counted in bytes or packets."""

    def setQueueSize(self, size):
        """Set the maximum queue length to the given size

        Arguments:
          size:Integer -- Maximum queue length, counted in bytes.
        Return value: None.
        """
        self._maxLen = size

    def getQueueSize(self):
        """Return the maximum queue length, counted in bytes."""
        return self._maxLen

    def setReceiver(self, rcvFun):
        """Set the function to be called to transmit an element.

        This function is called when an element is available and the
        queue is not blocked.

        Arguments:
          rcvFun:Function -- Function to send an element. Type: f(el)-->None.
        Return value: None.
        """
        self._rcvFun = rcvFun

    def put(self, element, *args):
        """Add an element to the queue.

        If the queue is not blocked, call _dequeue to send the element
        to the receiver target.
        Arguments:
          element:Any type -- Data element to be added to the queue
          *args:List -- Optional arguments for the specific scheduler
        Return value: None
        """
        self._enqueue(element, args)
        if not self._blocked:
            el = self._dequeue()
            if el != None and not self._blocked:
                self._blocked = True
                self._rcvFun(el)

    def get(self):
        """Actively retrieve an element from the queue.

        If the queue is blocked, None is returned.
        """
        if not self._blocked:
            return self._dequeue()
            
    def _enqueue(self, element, *args):
        """Discipline specific method to add an element to the queue.

        Arguments:
          element:Any type -- Data element to be added to the queue
          *args:List -- Optional arguments for the specific scheduler
        Return value: None
        """
        virtual

    def _dequeue(self):
        """Discipline specific method to retrieve an element from the queue."""
        virtual

    def resume(self):
        """Unblock the queue and send the next element, if available.

        This method is called from the receiver as soon as a previous send
        is finished.
        """

        self._blocked = False
        el = self._dequeue()
        if el != None:
            self._blocked = True
            self._rcvFun(el)

            
class DropTail(Queue):
    """FIFO queue that drops packets upon queue overflow.

    The queue length is counted in bytes."""

    def __init__(self):
        Queue.__init__(self)
        self._queue = []
        """Actual queue containing the queued elements."""
        self._len = 0
        """Current length of the queue, measured in bytes."""

        ### Statistics
        self.octetsDropped = 0L
        """Total number of dropped bytes."""
        self.octetsAccepted = 0L
        """Total number of bytes accepted for transmission."""

    def currentOccupation(self):
        """Return the number of bytes waiting in the queue."""
        return self._len

    def _enqueue(self, element, *args):
        """Enqueue the element, if there is sufficient space. Else drop it.

        Arguments:
          element:Any type -- Data element to be added to the queue
          *args:List -- Ignored
        Return value: None
        """
        lth = len(element)
        if lth+self._len <= self._maxLen:
            self._len += lth
            self.octetsAccepted += lth
            self._queue.append(element)
        else:
            self.octetsDropped += lth

    def _dequeue(self):
        """Retrieve an element from the queue.

        Return value: Element, or None, if the queue is empty
        """
        if self._len > 0:
            el = self._queue.pop(0)
            self._len -= len(el)
            return el
        else:
            return None


class PrioQueue(Queue):
    """Priority queue with limited total queue size.

    The queue length is counted in bytes."""

    def __init__(self):
        Queue.__init__(self)
        self._queues = {}
        """Dictionary of queues. Type: Priority --> Queue."""
        self._priorities = []
        """List of priorities, in ascending order."""
        self._len = 0
        """Current length of the queue, measured in bytes."""

        ### Statistics
        self.octetsDropped = 0
        """Total number of dropped bytes."""
        self.octetsAccepted = 0
        """Total number of bytes accepted for transmission."""

    def currentOccupation(self):
        """Return the number of bytes waiting in the queue."""
        return self._len

    def _enqueue(self, element, *args):
        """Enqueue the element, if there is sufficient space. Else drop it.

        Arguments:
          element:Any type -- Data element to be added to the queue
          *args:List of arguments -- Contains as only element the priorty.
        Return value: None
        """
        lth = len(element)
        if lth+self._len <= self._maxLen:
            self._len += lth
            self.octetsAccepted += lth
            priority = args[0]
            if priority not in self._queues:
                self._queues[priority] = []
                self._priorities.append(priority)
                self._priorities.sort()
            self._queues[priority].append(element)
        else:
            print "Drop"
            self.octetsDropped += lth

    def _dequeue(self):
        """Retrieve an element from the queue.

        Return value: Element, or None, if all queues are empty
        """
        el = None
        if self._len > 0:
            for priority in self._priorities:
                queue = self._queues[priority]
                if len(queue) > 0:
                    el = queue.pop(0)
                    self._len -= len(el)
                    break
        return el


##########################################################################
### Test code
##########################################################################

if __name__ == '__main__':

    #################################
    # Test DropTail queue : Put, Receiver, Get, Blocking, Resume, Length, Drop
    numRcv = 0
    lastEl = None
    def rcv(el):
        global numRcv, lastEl
        numRcv += 1
        lastEl = el
    
    q = DropTail()
    q.setQueueSize(100)
    q.setReceiver(rcv)

    # Test put and receiver
    q.put("1")
    assert(numRcv == 1)
    assert(lastEl == "1")
    assert(q._len == 0)
    assert(q._blocked)
    assert(q.octetsAccepted == 1)

    # Test put and blocking
    q.put("22")
    assert(numRcv == 1)
    assert(q._len == 2)
    assert(q._blocked)
    q.resume()
    assert(numRcv == 2)
    assert(lastEl == "22")
    assert(q._len == 0)
    assert(q._blocked)
    q.resume()
    assert(q._blocked == False)
    assert(q.octetsAccepted == 3)

    # Test queueing
    q.put("333")
    assert(numRcv == 3)
    assert(lastEl == "333")
    q.put("4"*50)
    q.put("5"*50)
    assert(numRcv == 3)
    assert(lastEl == "333")
    assert(q._len == 100)
    assert(q.octetsAccepted == 106)
    assert(q.octetsDropped == 0)
    q.put("6")
    assert(q._len == 100)
    assert(q.octetsDropped == 1)
    q.resume()
    assert(numRcv == 4)
    assert(lastEl == "4"*50)
    assert(q._len == 50)
    assert(q.octetsDropped == 1)
    q.put("7"*51)    
    assert(q._len == 50)
    assert(q.octetsDropped == 52)
    q.resume()
    assert(numRcv == 5)
    assert(lastEl == "5"*50)
    q.resume()
    assert(numRcv == 5)
    assert(lastEl == "5"*50)
    print "All tests passed"
    
    
