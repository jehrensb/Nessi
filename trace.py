# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: August 2003
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

"""The following trace modes are implemented:
  1. Explicit trace
     Tracing of values is triggered explicitly by a command in the
     simulation model.
  2. Sampling
     An user provided function is evaluated periodically and the return
     value is traced. Time intervals between sampling can be uniform or
     exponentially distributed.
  3. Variable tracing 
     A variable is traced each time it changes its value.
     @@@ To be done @@@
  4. Activity tracing:
     The activities of multiple actors are traced and can be visualized
     to show the coordination of actions of different protocol entities.
  5. Packet tracing
     Traces the content of send or received packets, similar to Ethereal.
     @@@ To be done @@@

Collected values may be used interactively (during the simulation) or written
to a file. Interactive trace visualization is possible by registering a
callback ('listener') for a trace. Each time a new value is collected, the
callback is called with the new value and the current time.

Collection of trace values and writing using trace values is strictly
separated. Trace collection is called by the protocol entities and may happen
at any time. Writing to trace files or listening to trace values must be
explicitly activated by a simulation script (e.g., using startFileTrace).
"""

__all__ = ["TraceCollector", "SamplerManager", "ActivityTracer"]

import struct
from random import expovariate


class TraceCollector(object):
    """Receive trace events and publish them using the Observer pattern.

    The class receives trace values and uses them in two ways:
    1. If file traces have been registered (using startFileTrace), then the
    value is written to all registered files, together with a the current
    simulation time. Multiple trace files may be registered per trace id.
    2. If listeners (observers) have registered callbacks for the trace, then
    the callbacks are called with the new trace value. This can be used to
    interactively visualize the simulation behavior.
    """

    def __init__(self,timeFunction):
        """
        Arguments:
          timeFunction:Function void --> float -- Returns the current time.
        Return value: None.
        """
        self._timefun = timeFunction
        """Function that returns the current time. Type: f: void --> float."""
        self._traceFiles = {}
        """Dictionariy of trace files. Type: Dict: id:Any Type --> file."""
        self._traceListeners = {}
        """Dictionary of listener callbacks. Type: Dict id --> [functions]."""

    def __del__(self):
        """Destructor. Close all open trace files."""
        for fileList in self._traceFiles.values():
            for f in fileList:
                f.close()

    def startFileTrace(self, id, filename, mode='ascii'):
        """Register a new trace file

        Arguments:
          id:Any type -- User chosen id of the trace.
          filename:String -- Name of the file to which the trace is written.
          mode:'ascii' or 'bin' -- Format of the trace file.
        Return value: None.
        """
        if mode == 'bin':
            mode="wb"
        else:
            mode="w"
        fileList = self._traceFiles.setdefault(id,[])
        if filename not in [f.name for f in fileList]:
            f = file(filename, mode)
            fileList.append(f)

    def stopFileTrace(self, id, filename):
        """Stop writing trace values to a file.
        
        Arguments:
          id:Any type -- User chosen id of the trace. 
          filename:String -- Name of the file to which the trace is written.
        Return value: None.
        """
        for f in self._traceFiles.get(id,[]):
            if f.name == filename:
                f.close()
                self._traceFiles[id].remove(f)
                break

    def flushFileTraces(self):
        """Write all trace data to the file but leave files open.

        Only call this method if you want to read the trace files before
        you have stopped the file traces.
        """
        for l in self._traceFiles.values():
            for f in l:
                f.flush()

    def registerListener(self, id, callback):
        """Register a callback to call when a trace value is collected.

        Arguments:
          id:Any type -- Trace for which the listener is registered.
          callback:Function object -- Function of the lister to be called
                                      when a new trace value is collected.
                                      Type: callback(time, id, value) --> None.
        Return value: None.
        """
        listenerList = self._traceListeners.setdefault(id,[])
        if callback not in listenerList:
            listenerList.append(callback)

    def unregisterListener(self, id, callback):
        """Unregister a callback of a listener.

        Arguments:
          id:Any type -- Trace for which the listener is registered.
          callback:Function object -- Callback that has been registered.
        Return value: None.
        """
        if id in self._traceListeners and callback in self._traceListeners[id]:
            self._traceListeners[id].remove(callback)

    def trace(self, id, value):
        """Collect a trace value.

        The trace value may be written to trace files or passed to listeners.

        Arguments:
          id:Any type -- Id of the trace. Used to find registered observers.
          value:Any type -- Value to be written to the file.
                            If the trace file is binary mode, then the value
                            must be numeric (it will be written as double).
        Return value: None.
        """
        for f in self._traceFiles.get(id,[]):
            if f.mode == "w":
                f.write("%0.12f %s\n" % (self._timefun(), str(value)))
            elif f.mode == "wb":
                f.write(struct.pack("dd", self._timefun(), value))

        for callback in self._traceListeners.get(id,[]):
            callback(self._timefun(), id, value)


class SamplerManager(object):
    """Peridical sampling of values.

    Sampling periodically evaluates a function and passes the resulting
    value to a tracing function. The intervals between successive evaluations
    can have a uniform or exponential distribution.
    """

    def __init__(self, traceFunction, timeFunction, scheduleFunction):
        self._traceFunction = traceFunction
        """Function to be called when a new sample value is available.
        Type: f(id,sample_value) --> None, where id is the trace id."""

        self._timeFunction = timeFunction
        """Returns the current time.
        Type f() --> Numeric"""

        self._scheduleFunction = scheduleFunction
        """Function that allows the scheduling of an action after a delay.
        Type: f(delay, action) --> None."""

    def newSampler(self, id, f, interval, type='uniform', start=0.0):
        """Create an sampler which evaluates the given function periodically.

        The values are collected for the trace with the given Id. 
        
        Arguments:
          id:Any type -- Id of the trace.
          f:Function object -- Function to evaluate. Type: f() --> AnyType.
          interval:Numeric -- Mean sampling interval, measured in seconds.
          type:'uniform' or 'exponential' -- Sampling interval distribution.
          start: Numeric -- Delay from now after which the sampler is started.
        Return value: None.
        """
        if type == 'uniform':
            def sampler():
                self._traceFunction(id, f())
                self._scheduleFunction(interval, sampler)
        elif type == 'exponential':
            lmbda = 1.0/interval
            def sampler():
                self._traceFunction(id, f())
                self._scheduleFunction(expovariate(lmbda), sampler)
        else:
            raise ValueError("Unknown sampling type: " + str(type))
        self._scheduleFunction(start, sampler)


class ActivityTracer(object):
    """Manager for activity traces.

    Activity traces indicate what action a protocol entity performs at a given
    time. Activity traces contain information that allows drawing activity
    diagrams. An activity diagram of MAC entities could look like this:
    
        | Collision   | Backoff       | Sending    |        | Sending
    A1:  xxxxxxxxxxxxx ...............  ++++++++++++          ++++++++++

          | Collision | Backoff           | Defer   | Send |    | Receiving
    A2:    xxxxxxxxxxx ...................           xxxxxxx      ###########
    
    The activities of different actors (A1, A2) are shown in time. An
    activity is visualized by a text (e.g. 'Collision') and a bar from the
    start to the end of the activity. Bars may be drawn in different colors,
    different thickness and different styles (solid, hatched, ...).

    To indicate an activity, actors call the method 'activity'.
    If the actor of the activity has not been registered for tracing,
    the indication is simply discarted.
    To actually do something with the activity indication of one or several
    actors, you have to register them with the method registerActor.
    Multiple actors can be registered to the same trace ID
    However, for a trace, the activities of multiple actors are grouped
    together. This is done using the method 'registerActor' that registers
    an actor for a trace, given by its trace id.

    The activities are thus collected to the same trace and can be written to
    a file or visualized in real time.
    """
    
    def __init__(self, traceCollector):
        self._traceCollector = traceCollector
        self._traceIdPerActor = {}
        """Trace Id which collectes the activities of an actor."""

    def registerActor(self, actor, traceId):
        """Start tracing activities of an actor to the given trace ID.

        Activities of multiple actors can be mapped to a trace.
        Example: to trace the activities of the MAC sublayer of certain NIUs,
        choose a trace id (e.g., 'MAC activities') and register the MAC
        protocol entities of all concerned NIUs for this traceID.

        An actor may be registered for multiple traces.

        Arguments:
          actor:ProtocolEntity -- Entity whose actions shall be traced.
          traceId:Any type -- Id of the trace which collects the activities.
        Return value: None.
        """
        idList = self._traceIdPerActor.setdefault(actor, [])
        if traceId not in idList:
            idList.append(traceId)

    def unregisterActor(self, actor, traceId=None):
        """Stop tracing activities of an actor to the given traceId.

        If traceId is omitted, all traces of the actor are stopped.

        Arguments:
          actor:ProtocolEntity -- Entity whose activities are traced.
          traceId:Any type -- Id of the trace from which the actor is deleted.
                              If omitted, then all traces of the actor are 
                              stopped.
        Return value: None.
        """
        if traceId == None:
            self._traceIdPerActor[actor] = []
        else:
            self._traceIdPerActor[actor].remove(traceId)

    def activity(self, actor, subactor=None, text="", *graphic):
        """Collect an activity indication.

        If the actor is registered for tracing, then the activity indication is
        passed to a tracing function. Otherwise it is simply discarted.
        The information passed to the trace function has the format:
        'actor_name.subactor#text#graphic'.

        Arguments:
          actor:ProtocolEntity -- Entity that performs the activity.
          subactor:String -- Optional additional indication of the part of the
                             actor that performs the activity (eg. 'rx', 'tx').
          text:String -- Short text describing the activity.
                         E.g., 'Backoff' or 'Send'. May be empty to indicate
                         the end of the previous activity.
          graphic: -- Either empty to indicate the end of the last activity
                      or a tuple (color, size, style).
                      color:String -- Indicated bar color (e.g., 'blue')
                      size:integer -- indicates bar thickness
                                      0=thick, 1=middle, 2=thin, 3=line, ...
                      style:integer -- Indicates the bar style, e.g., solid,
                                       hatch, ... See doc or try it out.
        Return value: None.
        """
        
        idList = self._traceIdPerActor.get(actor, [])
        if not idList:
            # Actor is not register for tracing. Discard indication
            return
        
        # Construct a string 'actorname.subactor#text#graphic'
        actorName = actor.fullName
        if subactor:
            actorName += "." + subactor
        if graphic:
            # Graphic must be a tuple (color, weight, style)
            graphic = "%s,%d,%d"%graphic
        else:
            graphic = ""
        s = '%s#%s#%s'%(actorName, text, graphic)
        for traceId in idList:
            self._traceCollector.trace(traceId, s)


# @@@ Maybe provide functions to switch diffent traces off completely by
# @@@ redefining the public functions.

        
