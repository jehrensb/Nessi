#!/usr/bin/env python

# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger; IICT HEIG-VD
# Creation: January 2005
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

"""Graphical user interface for the simulator.

The simulation controller allows a user to
  - load simulation files
  - start, stop, restart and pause simulations
  - manage the plotting of traces during the simulation
  - manage the plotting of activity diagrams during the simulation
  - change simulation and node parameters via command terminals.
  """

import os
import os.path
import sys
import imp
import time
from threading import Thread
import wx
import wx.py.shell
from wx.xrc import *
import wx.lib.dialogs

sys.path.append(os.path.abspath(os.getcwd()+"/.."))

# Play a dirty trick on the simulator: We redefine the scheduler with another
# scheduler that makes itself globally available.
# The simulation controller can then change its behavior.
# @@@ This is dirty, but I don't know a better way to obtain the same effect.
import nessi.scheduler
OldScheduler=nessi.scheduler.Scheduler
class MyScheduler(OldScheduler):
    def __init__(self,*args):
        global GLOBAL_simConScheduler
        OldScheduler.__init__(self,*args)
        GLOBAL_simConScheduler = self  
nessi.scheduler.Scheduler=MyScheduler

import nessi.simulator
from plotwin import PlotWin

class SimCon(wx.App):
    """Simulation controller with graphical user interface"""
    simStatus = None

    def OnInit(self):
        self.res = XmlResource("simcon_mainwin.xrc")
        self.initFrame()
        self.initMenu()
        self.initToolbar()
        self.initApplication()
        self.gui_frame.Show(1)
        self.SetTopWindow(self.gui_frame)
        return True

    def initFrame(self):
        self.gui_frame = self.res.LoadFrame(None, "mainframe")
        self.gui_statusbar = XRCCTRL(self.gui_frame, "statusbar")
        self.gui_console = XRCCTRL(self.gui_frame, "console")
        self.gui_simtime_text = XRCCTRL(self.gui_frame, "simtime_text")
        self.gui_simtime_slider = XRCCTRL(self.gui_frame, "simtime_slider")
        self.gui_delay_text = XRCCTRL(self.gui_frame, "delay_text")
        self.gui_delay_text.SetValue("0 ms")
        self.gui_delay_slider = XRCCTRL(self.gui_frame, "delay_slider")
        wx.EVT_COMMAND_SCROLL(self.gui_frame, XRCID("delay_slider"),
                                         self.onDelayScroll)
        wx.EVT_COMMAND_SCROLL_ENDSCROLL(self.gui_frame, XRCID("delay_slider"),
                                         self.newSimDelay)
        wx.EVT_COMMAND_SCROLL_THUMBRELEASE(self.gui_frame,
                                           XRCID("delay_slider"),
                                           self.newSimDelay)
    def initMenu(self):
        bindings = (
            ("file_open", self.onFileOpen),
            ("file_close", self.onFileClose),
            ("file_exit", self.onFileExit),
            
            ("trace_newFiletrace", self.onNewFileTrace),
            ("trace_deleteFiletrace", self.onDelFileTrace),
            
            ("plot_plotwin", self.onPlotWin),
            ("plot_activitywin", self.onActivityWin),

            ("help_about", self.onHelpAbout))
        for id,fun in bindings:
            wx.EVT_MENU(self.gui_frame, XRCID(id),fun)

    def initToolbar(self):
        self.toolbar = XRCCTRL(self.gui_frame, "toolbar")
        wx.EVT_MENU(self.gui_frame, XRCID("tool_open"), self.onFileOpen)
        wx.EVT_MENU(self.gui_frame, XRCID("start_sim"), self.onStartSim)
        wx.EVT_MENU(self.gui_frame, XRCID("pause_sim"), self.onPauseSim)
        wx.EVT_MENU(self.gui_frame, XRCID("stop_sim"), self.onStopSim)
        wx.EVT_MENU(self.gui_frame, XRCID("restart_sim"), self.onRestartSim)
        wx.EVT_MENU(self.gui_frame, XRCID("step_sim"), self.onStepSim)
        wx.EVT_MENU(self.gui_frame, XRCID("plot_win"), self.onPlotWin)

    def initApplication(self):
        """Initialize application parameters"""
        self.simFile=None
        self.simMaxTime=0
        self.simRandomSeed=0
        self.fileTraces=[] # List of currently registered file traces
        self.plotwins=[] # List of active plot windows

        # Redefine some simulator function to allow intercepting calls
        # @@@ Dirty but it works
        def mySimFunRUN(until):
            self.simMaxTime=until
        self.simFunRUN = nessi.simulator.RUN
        nessi.simulator.RUN = mySimFunRUN # Redefine the simulator function

        def mySimFunRandomSeed(seed):
            self.simRandomSeed=seed
            self.simFunRandomSeed(seed)
        self.simFunRandomSeed=nessi.simulator.RANDOM_SEED
        nessi.simulator.RANDOM_SEED=mySimFunRandomSeed # Redefine the funcion

        self.simFunDelayfunc = GLOBAL_simConScheduler._delayfunc

    #---------------------------------------------------------------
        
    def onFileOpen(self,evt):
        """Select simulation file via dialog and load the simulation"""
        dlg = wx.FileDialog(
            self.gui_frame, message="Choose a simulation file",
            defaultDir=os.getcwd(), 
            defaultFile="",
            wildcard="Python source (*.py)|*.py|All files (*.*)|*.*",
            style=wx.OPEN | wx.CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            simFile = os.path.abspath(dlg.GetPaths()[0])
            self.loadSimulation(simFile)
            self.newConsole()

    def onFileClose(self,evt):
        pass

    def onFileExit(self,evt):
        pass

    def onNewFileTrace(self,evt):
        tracedlg=self.res.LoadDialog(None, "dlgNewFileTrace")
        wx.EVT_BUTTON(tracedlg, XRCID("newFileTrace_OK"),
                      lambda evt: tracedlg.EndModal(wx.ID_OK))
        wx.EVT_BUTTON(tracedlg, XRCID("newFileTrace_CANCEL"),
                      lambda evt: tracedlg.EndModal(wx.ID_CANCEL))
        def fileDlgF(evt):
            filedlg = wx.FileDialog(
                tracedlg, message="Write trace to file...",
                defaultDir=os.getcwd(), 
                defaultFile="file.trace",
                wildcard="All files (*.*)|*.*",
                style=wx.SAVE)
            if filedlg.ShowModal() == wx.ID_OK:
                file = os.path.abspath(filedlg.GetPaths()[0])
                XRCCTRL(tracedlg,"newFileTrace_traceFile").SetValue(file)
        wx.EVT_BUTTON(tracedlg, XRCID("newFileTrace_FileDlg"), fileDlgF)

        if tracedlg.ShowModal() == wx.ID_OK:
            traceID = XRCCTRL(tracedlg, "newFileTrace_traceID").GetValue()
            traceFile = XRCCTRL(tracedlg, "newFileTrace_traceFile").GetValue()
        if traceID and traceFile:
            nessi.simulator.START_FILE_TRACE(traceID, traceFile)
            self.fileTraces.append((traceID,traceFile))

    def onDelFileTrace(self,evt):
        lst = ["Trace ID: %s to file: %s"%(id,f) for id,f in self.fileTraces]
        dlg = wx.lib.dialogs.MultipleChoiceDialog(
            self.gui_frame,
            "Choose file traces to delete","Delete file traces",lst)
        if (dlg.ShowModal() == wx.ID_OK):
            selection=list(dlg.GetValue())
            selection.sort()
            selection.reverse()
            for sel in selection:
                del self.fileTraces[sel]
        dlg.Destroy()

    def onPlotWin(self,evt):
        plotwin=PlotWin(self.gui_frame)
        self.plotwins.append(plotwin)
    
    def onActivityWin(self,evt):
        pass

    def onHelpAbout(self,evt):
        pass

    #----------------------------------------------------------------
    # Controller functions for the simulator
    # The behavior is controlled by the variable simStatus. It has the
    # following transitions:
    # None
    #   |--- loadSimulation ---> Initialized
    #
    # Initialized
    #   |--- onStartSim ---> Running
    #   |--- onFileClose ---> Initial
    #
    # Running
    #   |--- simFinished ---> Finished
    #   |--- onStopSim ---> Finished
    #   |--- onPauseSim ---> Paused
    #   |--- onStepSim ---> Stepping
    #
    # Paused
    #   |--- onStartSim | onPauseSim ---> Running
    #   |--- onStopSim ---> Finished
    #
    # Stepping
    #   |--- onStepSim ---> Stepping (performs next step)
    #   |--- simFinished ---> Finished (stepped through last event)
    #   |--- onStartSim ---> Running
    #   |--- onStopSim ---> Finished
    #
    # Finished
    #   |--- onRestartSim ---> Initialized
    #   |--- onFileClose ---> None
      
    Initialized,Running,Paused,Stepping,Finished = [1,2,3,4,5]
    
    def onStartSim(self,evt):
        if self.simStatus==self.Initialized:
            nessi.simulator.SCHEDULE(0.0,self.guiUpdater)
            nessi.simulator.SCHEDULE(self.simMaxTime, self.simFinished,
                                     priority=sys.maxint)
            self.gui_simtime_slider.SetRange(0.0,self.simMaxTime)
            self.gui_frame.SetStatusText("Simulation running...")
            self.simStatus=self.Running
            self.simFunRUN(self.simMaxTime)
        elif self.simStatus==self.Paused:
            self.simStatus=self.Running
            self.gui_frame.SetStatusText("Simulation running...")
            nessi.simulator.CONTINUE()
        elif self.simStatus==self.Stepping:
            self.simStatus=self.Running
            self.gui_frame.SetStatusText("Simulation running...")
            nessi.simulator.CONTINUE()

    def onPauseSim(self,evt):
        if self.simStatus==self.Running:
            nessi.simulator.HALT()
            self.simStatus=self.Paused
            self.setCurrentSimTime(nessi.simulator.TIME())
            self.updateTraces(self.simStatus)
            self.gui_frame.SetStatusText("Simulation halted")
        elif self.simStatus==self.Paused:
            self.simStatus=self.Running
            self.gui_frame.SetStatusText("Simulation running...")
            nessi.simulator.CONTINUE()
            
    def onStopSim(self,evt):
        if self.simStatus in (self.Running,self.Paused,self.Stepping):
            nessi.simulator.TERMINATE()
            self.simStatus=self.Finished
            self.setCurrentSimTime(nessi.simulator.TIME())
            self.updateTraces(self.simStatus)
            self.gui_frame.SetStatusText("Simulation terminated")

    def onStepSim(self,evt):
        if self.simStatus in (self.Stepping, self.Running):
            self.simStatus=self.Stepping
            nessi.simulator.STEP()
            self.setCurrentSimTime(nessi.simulator.TIME())
            self.updateTraces(self.simStatus)
            self.gui_frame.SetStatusText("Stepping mode...")            

    def onRestartSim(self,evt):
        if self.simStatus==self.Finished:
            self.loadSimulation(self.simFile)
            self.simStatus=self.Initialized
            self.setCurrentSimTime(0.0)
            self.simFunRandomSeed(self.simRandomSeed)
            self.updateTraces(self.simStatus)
            self.gui_frame.SetStatusText("Simulation reloaded")

    def onResetDelay(self,evt):
        pass

    def onDelayScroll(self,evt):
        delay = self.gui_delay_slider.GetValue()
        self.gui_delay_text.SetValue("%d ms"%delay)
        # This is necessary for wxGTK
        self.newSimDelay(evt)

    def newSimDelay(self,evt):
        stepDelay = self.gui_delay_slider.GetValue()
        if stepDelay == 0:
            # Install the original delay function
            GLOBAL_simConScheduler._delayfunc = self.simFunDelayfunc
        else:
            stepDelay /= 1000.0 # counted in milliseconds
            def myDelayfunc(delay):
                self.setCurrentSimTime(nessi.simulator.TIME())
                self.Yield()
                time.sleep(stepDelay)
                self.simFunDelayfunc(delay)
            GLOBAL_simConScheduler._delayfunc = myDelayfunc
        
    #----------------------------------------------------------------

    def loadSimulation(self,simFile):
        """Load the simulation file"""
        path=os.path.dirname(simFile)
        pyfile=os.path.basename(simFile)
        name,ext=os.path.splitext(pyfile)
        try:
            file,pathname,desc = imp.find_module(name,[path,os.getcwd()])
        except ImportError, message:
            dlg = wx.MessageDialog(self.gui_frame, str(message),
                                   'File load error',
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        try:
            self.simModule = imp.load_module(name,file,simFile,desc)
        except Exception,message:
            dlg = wx.MessageDialog(self.gui_frame, str(message),
                                   'File import error',
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            file.close()
            return
        file.close()
        self.gui_frame.SetTitle("Nessi simulation controler: " + name)
        self.gui_frame.SetStatusText("Successfully loaded")
        self.simFile=simFile
        self.simStatus=self.Initialized
        return

    def newConsole(self):
        """Initialize a new shell environment and place it into the window."""
        consoleWin = self.gui_console.GetParent()
        consoleWin.GetSizer().Remove(self.gui_console)
        self.gui_console.Destroy()
        self.gui_console = wx.py.shell.Shell(parent=consoleWin,
                                             locals=self.simModule.__dict__)
        consoleWin.GetSizer().Add(self.gui_console, 1,wx.EXPAND)
        consoleWin.GetSizer().Layout()
        self.gui_console.Show()
        self.gui_console.SetFocus()
        
    def setCurrentSimTime(self,time):
        """Register the current simulation time"""
        self.currentSimTime = time
        self.gui_simtime_text.SetValue("%.6f"%time)
        self.gui_simtime_slider.SetValue(time)

    def guiUpdater(self):
        self.setCurrentSimTime(nessi.simulator.TIME())
        self.Yield()
        nessi.simulator.SCHEDULE(self.simMaxTime/10000.0,self.guiUpdater)
        
    def simFinished(self):
        """Update state after simulation is finished"""
        self.setCurrentSimTime(nessi.simulator.TIME())
        self.simStatus=self.Finished
        self.updateTraces(self.simStatus)
        self.gui_frame.SetStatusText("Simulation finished")

    def removeAllTraces(self):
        """Unregister all file traces"""
        while self.fileTraces:
            traceID,filename=self.fileTraces.pop()
            nessi.simulator.STOP_FILE_TRACE(traceID,filename)
        
    def updateTraces(self,status):
        if status in (self.Stepping, self.Paused, self.Finished):
            nessi.simulator.FLUSH_TRACE_FILES()
        elif status == self.Initialized:
            for id,f in self.fileTraces:
                nessi.simulator.STOP_FILE_TRACE(id,f)
                nessi.simulator.START_FILE_TRACE(id,f)
            for plotwin in self.plotwins:
                plotwin.simReloaded()
    
#----------------------------------------------------------------
#----------------------------------------------------------------        
if __name__ == "__main__":
    _simcon = SimCon(0)
    _simcon.MainLoop()
