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

""" Simulation engine.

The scheduler is the simulation engine of the simulator. It allows other
objects to schedule simulation events at a given simulation time. The
scheduler takes care of executing the events in the correct chronological
order.

The functions are implemented by a class Scheduler. It is a simple
list based and single threaded discrete event scheduler.
"""

__all__ = ["Scheduler"]

import bisect

class Scheduler:
    """Discrete event scheduler.

    Simple list based and single threaded event scheduler.
    """
    
    def __init__(self):
        self.queue = []
        self.simtime = 0
        self.singleStep = False
        self.running = False
        self.maxtime = 10e300

    def now(self):
        """Returns the current simulation time as a float."""
        return self.simtime

    def enterabs(self, time, action, arguments=(), priority=10):
        """Schedule a new action at an absolute time.

        Arguments:
            time:float -- time at which the action is to be executed    
            action:function -- function to be called by the scheduler
            arguments:tuple -- tuple of arguments required by the action
            priority:integer -- priority of the action. Action scheduled at the
                same time are ordered with decreasing priorities
        Return value: eventId -- Handle of the scheduled event.
        """
        if self.simtime <= time <= self.maxtime:
            event = time, priority, action, arguments
            bisect.insort_right(self.queue, event)
            return event # The ID
        else:
            return (time, priority, action, arguments)

    def enter(self, delay, action, arguments=(), priority=10):
        """Schedule a new action after a delay.

        Arguments:
          delay:float -- delay after which the action is to be executed
          action:function -- function to be called by the scheduler
          arguments:tuple -- tuple of arguments required by the action
          priority:integer -- priority of the action. Action scheduled at the
                              same time are ordered with increasing priorities
        Return value: eventId -- Handle of the scheduled event.
        """
        time = self.simtime + delay
        return self.enterabs(time, action, arguments, priority)

    def cancel(self, event):
        """Cancel a previously scheduled event.

        Arguments:
            eventID -- Event handle as returned by the SCHEDULE functions.
        Return value: None.
        """
        try:
            self.queue.remove(event)
        except ValueError:
            # This should only happen if the event time is passed the maxtime
            time,priority,action,arguments = event
            if time <= self.maxtime:
                # This is a program error of the simulation
                raise RuntimeError("CANCEL of non-existing event:\n" +
                                   "  Time: %s\n  Action: %s\n  Arguments: %s."
                                   % (str(time), str(action), str(arguments)))

    def empty(self):
        """Return True if the event queue is empty, otherwise false."""
        return len(self.queue) == 0

    def run(self,until=10e300):
        """Run the simulation.

        The scheduler increases the simulation time and calls the scheduled
        actions at their schedule times.

        Arguments:
            until:float -- Simulation time at which the simulation ends.
        Return value: last simulation time.
        """
        self.maxtime = until
        self.simtime = 0
        self.running = True
        lastEventTime = self._eventloop()
        return lastEventTime

    def cont(self):
        """Continue a halted or single-stepped simulation.
        
        The simulator continues with the next scheduled event,
        without single step, if this had been active before.
        
        Return value: last simulation time.
        """
        if self.singleStep:
            self.singleStep=False
            self.running=True
            lastEventTime = self._eventloop()
            return lastEventTime
        elif self.running == False:
            self.running=True
            lastEventTime = self._eventloop()
            return lastEventTime

    def halt(self):
        """Halt the current simulation.

        The scheduler stops to increase the simulation time but all scheduled
        events are kept. The simulation can be restarted with continue.

        Return value: None.
        """
        self.running = False

    def terminate(self):
        """Stop the simulation and delete all scheduled events.

        A terminated simulation cannot be restarted.

        Return value: None.
        """
        del self.queue[:] # delete all pending events
        if self.running and not self.singleStep:
            # Event loop is active. Let it terminate and clean up
            self.maxtime = 0.0 # do not accept new events anymore
        else:
            # Event loop is not active. I reinitialze myself.
            self.running=False
            self.reinitialize()

    def step(self):
        """Step a single event forward.

        Enters stepping mode, if not yet active.

        Return value: last simulation time.
        """
        if self.running:
            if self.singleStep:
                return self._eventloop()
            else:
                self.singleStep=True

    def isrunning(self):
        """Return True if the simulation is running, otherwise False."""
        return self.running

    def reinitialize(self):
        """Clean up to prepare for a new simulation run.

        Can only be called if the simulation is not running.
        """
        if not self.running:
            print "Cleaning up"
            del self.queue[:]
            self.simtime = 0.0
            self.maxtime = 10e300
            self.running = False
            self.singleStep = False

    # Private methods ------------------------------------------------

    def _delayfunc(self, delay):
        """Advance the simulation time by a delay.

        This method may be overwritten by a subclass to provide a different
        behavior, e.g., sleep for a while.
        """
        self.simtime = self.simtime+delay
        
    def _eventloop(self):
        """Execute the scheduled events at their event time.

        Returns the event time of the last executed event.
        """
        q = self.queue
        while q and self.running:
            time, priority, action, arguments = q.pop(0)
            now = self.simtime
            if now < time:
                self._delayfunc(time - now)
            void = action(*arguments)
            
            if self.singleStep and q:
                # Single step mode and simulation is not yet finished. Return
                return self.simtime
            
        # Simulation has been halted, terminated or it has finished.
        self.running = False
        if q:
            # Events remaining. I have been halted.
            return self.simtime
        else:
            # No events remain. Simulation terminated or finished. Clean up.
            lastEventTime = self.simtime
            self.reinitialize()
            return lastEventTime

