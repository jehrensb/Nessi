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

"""Main module of the simulator. Has to be imported by a simulation script.

This module simply provides the general simulator functionalities by importing
them from the following modules:
  - scheduler
  - trace
  - random
It defines the following simulator functions to be called by protocol entities
or simulation scripts:

- SCHEDULE: Schedule a new action at a time relative from the current time.
- SCHEDULEABS: Schedule a new action at an absolute time.
- CANCEL: Cancel a scheduled event.
- TIME: Return the current simulation time.
- RUN: Start the simulation for the first time.
- CONTINUE: Continue a halted simulation.
- HALT: Halt the current simulation.
- TERMINATE: Terminate the current simulation.
- REINITIALIZE: Prepare the simulation for a new run.
- TRACE: Collect a trace value
- START_FILE_TRACE: Start writing a trace to a file
- STOP_FILE_TRACE: Stop writing a trace to a file
- FLUSH_TRACE_FILES: Empty write buffers and actually write all data onto disk
- REGISTER_LISTENER: Start passing trace values to an observer function
- UNREGISTER_LISTENER: Stop passing trace values to an observer function
- NEW_SAMPLER: Define a function that will collect trace values periodically
- ACTIVITY_INDICATION: Indicate that an actor performed an action
- REGISTER_ACTOR: Start collecting activity indications of an actor
- UNREGISTER_ACTOR: Stop collecting activity indications of an actor
- RANDOM_SEED: Initialize the random number generator with a seed
"""
__all__ = ["SCHEDULE", "SCHEDULEABS", "CANCEL", "TIME", "RUN", "CONTINUE",
           "HALT", "TERMINATE", "REINITIALIZE",
           "TRACE", "START_FILE_TRACE", "STOP_FILE_TRACE", "FLUSH_TRACE_FILES",
           "REGISTER_LISTENER", "UNREGISTER_LISTENER", "NEW_SAMPLER",
           "ACTIVITY_INDICATION", "REGISTER_ACTOR", "UNREGISTER_ACTOR",
           "RANDOM_SEED"]

import scheduler
import trace
import random

_sched = scheduler.Scheduler()
_traceCollector = trace.TraceCollector(_sched.now)
_activityTracer = trace.ActivityTracer(_traceCollector)
_samplerManager = trace.SamplerManager(_traceCollector.trace,
                                        _sched.now, _sched.enter)

# ======================================
# Define the public simulation functions
# ======================================

# Scheduler functions
# -------------------

SCHEDULE = _sched.enter
"""Schedule a new action after a delay.

Arguments:
    delay:float -- delay after which the action is to be executed
    action:function -- function to be called by the scheduler
    arguments:tuple -- tuple of arguments required by the action
    priority:integer -- priority of the action. Action scheduled at the
        same time are ordered with increasing priorities
Return value: eventId -- Handle of the scheduled event.
"""

SCHEDULEABS = _sched.enterabs
"""Schedule a new action at an absolute time.

Arguments:
    time:float -- time at which the action is to be executed    
    action:function -- function to be called by the scheduler
    arguments:tuple -- tuple of arguments required by the action
    priority:integer -- priority of the action. Action scheduled at the
        same time are ordered with decreasing priorities
Return value: eventId -- Handle of the scheduled event.
"""

CANCEL = _sched.cancel
"""Cancel a previously scheduled event.

Arguments:
    eventID -- Event handle as returned by the SCHEDULE functions.
Return value: None.
"""

TIME = _sched.now
"""Returns the current simulation time as a float."""

RUN = _sched.run
"""Run the simulation until it is halted, terminated, or finishes.

Arguments:
    until:float -- Simulation time at which the simulation ends.
Return value: last simulation time.
"""

HALT = _sched.halt
"""Halt the current simulation.

The scheduler stops to increase the simulation time but all scheduled
events are kept. The simulation can be restarted with CONTINUE.

Return value: None.
"""

CONTINUE = _sched.cont
"""Continue a halted or single-stepped simulation.

The simulator continues with the next scheduled event (without single step)

Return value: last simulation time.
"""

TERMINATE = _sched.terminate
"""Stop the simulation and delete all scheduled events.

A terminated simulation cannot be restarted.

Return value: None.
"""

STEP = _sched.step
"""Step a single event forward.

Return value: last simulation time.
"""

IS_RUNNING = _sched.isrunning
"""Return True if the simulation is running, otherwise False"""

REINITIALIZE = _sched.reinitialize
"""Clean up to prepare for a new simulation run.

Can only be called if the simulation is not running.
"""

# Trace functions
# ---------------

TRACE = _traceCollector.trace
"""Collect a trace value for use by a listener or to write it to a file.

Arguments:
    id:Any type -- Id of the trace.
    value:Any type -- Value to be written to the file.
        If the trace file is binary mode, then the value
        must be numeric (it will be written as double).
Return value: None.
"""

START_FILE_TRACE = _traceCollector.startFileTrace
"""Start writing trace values to a file.

Arguments:
    id:Any type -- User chosen id of the trace. Used in write/reset commands.
    filename:String -- Name of the file to which the trace is written.
    mode:'ascii' or 'bin' -- Format of the trace file. Default is 'ascii'.
Return value: None.
"""

STOP_FILE_TRACE = _traceCollector.stopFileTrace
"""Stop writing trace values to a file.

Arguments:
    id:Any type -- User chosen id of the trace. 
    filename:String -- Name of the file to which the trace is written.
Return value: None.
"""

FLUSH_TRACE_FILES = _traceCollector.flushFileTraces
"""Write all trace data to the file but leave files open.

Only call this method if you want to read the trace files before
you have stopped the file traces.
"""

REGISTER_LISTENER = _traceCollector.registerListener
"""Register a callback to call when a trace value is collected.

Arguments:
    id:Any type -- Trace for which the listener is registered.
    callback:Function object -- Function of the lister to be called
        when a new trace value is collected.
        Type: callback(time, id, value) --> None.
Return value: None.
"""

UNREGISTER_LISTENER = _traceCollector.unregisterListener
"""Unregister a callback of a listener.

Arguments:
    id:Any type -- Trace for which the listener is registered.
    callback:Function object -- Callback that has been registered.
Return value: None.
"""

NEW_SAMPLER = _samplerManager.newSampler
"""Create an sampler which evaluates the given function periodically.

The return values are collected for the trace with the given Id.
There is no method to delete a sampler during a running simulation.

Arguments:
    id:Any type -- Id of the trace.
    f:Function object -- Function to evaluate. Type: f() --> trace value.
    interval:Numeric -- Mean sampling interval, measured in seconds.
    type:'uniform' or 'exponential' -- Distribution of the sampling interval.
    start: Numeric -- Delay from now after which the sampler is started.
Return value: None.
"""

ACTIVITY_INDICATION = _activityTracer.activity
"""Collect an activity indication.

Activity indications are issued by protocol entities ('actors').
If the actor is registered for tracing, then the activity indication is
passed to a tracing function. Otherwise it is simply discarted.
The information passed to the trace function has the format:
'actor_name.subactor#text#graphic'.

A actually use an activity indications of an actor, you have to do the
following:
- Register the actor for tracing with a given trace ID using REGISTER_ACTOR.
  Multiple actors can be registered for the same trace ID.
- Register a listener or a file trace for the trace ID using REGISTER_LISTENER
  or START_FILE_TRACE.
  
Arguments:
    actor:ProtocolEntity -- Entity that performs the activity.
    subactor:String -- Optional additional indication of the part of the
        actor that performs the activity (eg. 'rx', 'tx').
    text:String -- Short text describing the activity.
        E.g., 'Backoff' or 'Send'. May be empty to indicate
        the end of the previous activity.
    graphic: -- Either empty to indicate the end of the previous activity
        or a tuple (color, size, style).
        color:String -- Indicated bar color (e.g., 'blue')
        size:integer -- indicates bar thickness
            0=thick, 1=middle, 2=thin, 3=line, ...
        style:integer -- Indicates the bar style, e.g., solid,
            hatch, ... See doc or try it out.
Return value: None.
"""

REGISTER_ACTOR = _activityTracer.registerActor
"""Start tracing activities of an actor to the given trace ID.

Activities of multiple actors can be mapped to the same trace ID.
Example: to trace the activities of the MAC entity of some NIUs,
choose a trace ID (e.g., 'MAC activities') and register the MAC
protocol entities of all concerned NIUs for this trace ID.

An actor may be registered for multiple traces.

Arguments:
    actor:ProtocolEntity -- Entity whose actions shall be traced.
    traceId:Any type -- Id of the trace which collects the activities.
Return value: None.
"""

UNREGISTER_ACTOR = _activityTracer.unregisterActor
"""Stop tracing activities of an actor to the given traceId.

If traceId is omitted, all traces of the actor are stopped.

Arguments:
    actor:ProtocolEntity -- Entity whose activities are traced.
    traceId:Any type -- Id of the trace from which the actor is deleted.
                        If omitted, then all traces of the actor are stopped.
Return value: None.
"""

def RANDOM_SEED(s):
    """Initialize the random number generator with a seed"""
    random.seed(s)
