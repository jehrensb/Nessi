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

"""Plot window for the GUI simulation controller

Based on example embedding_in_wx2.py of the matplotlib examples.
"""

import time
import os
import os.path
import array
import wx
from wx.xrc import *
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wx import NavigationToolbar2Wx
from matplotlib.figure import Figure
import nessi.simulator

ID_PLOT_TRACE = 101
ID_PLOT_LISTENER = 102
ID_CLEAR_PLOT = 103
ID_PLOT_PARAMETERS = 104
ID_TRACE_NEW_LINE = 105
ID_TRACE_ADD_LINE = 106
ID_TRACE_NEW_BAR = 107
ID_LISTENER_NEW_LINE = 108
ID_LISTENER_NEW_BAR = 109

homepath = os.getcwd()

class PlotWin(wx.Frame):
    
    def __init__(self,parent):
        self.parent=parent
        self.listeners = {}
        self.makeFrame()
        self.initMenu()
        self.initPopUpMenu()

    def makeFrame(self):
        global canvas #@@@@
        # Got this trick for a two stage creation from
        # http://wiki.wxpython.org/index.cgi/TwoStageCreation
        pre = wx.PreFrame()
        self.res = XmlResource(homepath+"/plotwin.xrc")
        self.res.LoadOnFrame(pre,self.parent,"plotwin")
        self.PostCreate(pre)
        self.SetBackgroundColour(wx.NamedColor("WHITE"))
        self.Show()

        self.figure = Figure()
        self.axes = [self.figure.add_subplot(111)]
        self.canvas = FigureCanvas(self, -1, self.figure)
        canvas = self.canvas #@@@@
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.Fit()
        self.addToolbar()

        
    def initMenu(self):
        self.menubar = XRCCTRL(self, "menubar") 
        bindings = (
            ("file_exit", self.onFileExit),
            ("layout_subplots", self.onLayout),
            ("help_about", self.onHelpAbout))
        for id,fun in bindings:
            wx.EVT_MENU(self, XRCID(id),fun)

    def initPopUpMenu(self):
        filetraceMenu=wx.Menu()
        filetraceMenu.Append(ID_TRACE_NEW_LINE, "New line plot...")
        filetraceMenu.Append(ID_TRACE_ADD_LINE, "Add line plot...")
        filetraceMenu.Append(ID_TRACE_NEW_BAR, "New bar plot...")
        
        filelistenerMenu=wx.Menu()
        filelistenerMenu.Append(ID_LISTENER_NEW_LINE, "New line plot...")
        filelistenerMenu.Append(ID_LISTENER_NEW_BAR, "New bar plot...")
        
        self.popup = wx.Menu()
        self.popup.AppendMenu(ID_PLOT_TRACE, "Plot file trace", filetraceMenu)
        self.popup.AppendMenu(ID_PLOT_LISTENER, "Plot from listener",
                              filelistenerMenu)
        self.popup.AppendSeparator()
        self.popup.Append(ID_CLEAR_PLOT, "Clear plot")
        self.popup.Append(ID_PLOT_PARAMETERS, "Plot parameters...")

        self.Bind(wx.EVT_MENU, self.onClearPlot, id=ID_CLEAR_PLOT)
        self.Bind(wx.EVT_MENU, self.onPlotParameters, id=ID_PLOT_PARAMETERS)
        self.Bind(wx.EVT_MENU, self.onTraceLine, id=ID_TRACE_NEW_LINE)
        self.Bind(wx.EVT_MENU, self.onTraceLine, id=ID_TRACE_ADD_LINE)
        self.Bind(wx.EVT_MENU, self.onTraceNewBar, id=ID_TRACE_NEW_BAR)
        self.Bind(wx.EVT_MENU, self.onListenerNewLine, id=ID_LISTENER_NEW_LINE)
        self.Bind(wx.EVT_MENU, self.onListenerNewBar, id=ID_LISTENER_NEW_BAR)

    def addToolbar(self):
        self.toolbar = NavigationToolbar2Wx(self.canvas)
        self.toolbar.Realize()
        if wx.Platform == '__WXMAC__':
            # Mac platform (OSX 10.3, MacPython) does not seem to cope with
            # having a toolbar in a sizer. This work-around gets the buttons
            # back, but at the expense of having the toolbar at the top
            self.SetToolBar(self.toolbar)
        else:
            # On Windows platform, default window size is incorrect, so set
            # toolbar width to figure width.
            tw, th = self.toolbar.GetSizeTuple()
            fw, fh = self.canvas.GetSizeTuple()
            # By adding toolbar in sizer, we are able to put it at the bottom
            # of the frame - so appearance is closer to GTK version.
            # As noted above, doesn't work for Mac.
            self.toolbar.SetSize(wx.Size(fw, th))
            self.sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        # update the axes menu on the toolbar
        self.toolbar.update()
        self.canvas.mpl_connect("button_press_event", self.onButtonPress)

    # ---------------------------------------------------------------------

    def onFileExit(self,evt):
        pass
        
    def onLayout(self,evt):
        dlg=self.res.LoadDialog(self, "layoutDlg")
        wx.EVT_BUTTON(dlg,XRCID("button_OK"),
                   lambda evt: dlg.EndModal(wx.ID_OK))
        wx.EVT_BUTTON(dlg,XRCID("button_Cancel"),
                   lambda evt: dlg.EndModal(wx.ID_CANCEL))
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            self.numRows = XRCCTRL(dlg, "rowSpin").GetValue()
            self.numCols = XRCCTRL(dlg, "colSpin").GetValue()
            self.newLayout()
        dlg.Destroy()

    def onButtonPress(self,evt):
        if not evt.inaxes:
            return
        if evt.button==wx.MOUSE_BTN_RIGHT and not self.toolbar._active:
            self.currentAxis = evt.inaxes
            x=evt.x
            y=self.canvas.GetSize().GetHeight()-evt.y
            self.PopupMenu(self.popup, wx.Point(x,y))

    def onTraceLine(self,evt):
        traceFile = self.openTraceFile()
        if not traceFile:
            return
        if evt.GetId() == ID_TRACE_NEW_LINE:
            self.currentAxis.clear()
        xvec=[]
        yvec=[]
        for line in traceFile:
            x,y=line.split()
            xvec.append(float(x))
            yvec.append(float(y))
        traceFile.close()
        self.currentAxis.plot(xvec,yvec)

    def onTraceNewBar(self,evt):
        traceFile = self.openTraceFile()
        if not traceFile:
            return
        data = {}
        for line in traceFile:
            # Lines have the format: time item1;item2;item3
            # where the items have the format: xvalue,yvalue
            t,line = line.split(' ',1)
            line = line.strip()
            if line:
                items=line.split(';')
                for item in items:
                    x,y=item.split(',')
                    data[int(x)]=float(y)
        traceFile.close()
        xvec=data.keys()
        yvec=data.values()
        self.currentAxis.bar(xvec,yvec)
        self.currentAxis.set_title("Trace: %s"%os.path.basename(traceFile.name))

    def onListenerNewLine(self,evt):
        result = self.newLineListenerDlg()
        if not result:
            return
        traceID,updateFreq,visiblePoints,keepInvisiblePoints = result
        if not traceID or not updateFreq or visiblePoints < 0:
            return
        self.onClearPlot(None)
        self.listeners[traceID] = LineListener(
            traceID, self.currentAxis, 1.0/updateFreq, visiblePoints,
            keepInvisiblePoints)

    def onListenerNewBar(self,evt):
        result = self.newBarListenerDlg()
        if not result:
            return
        traceID,updateFreq = result
        if not traceID or not updateFreq:
            return
        self.onClearPlot(None)
        self.listeners[traceID] = BarListener(
            traceID, self.currentAxis, 1.0/updateFreq) 

    def onClearPlot(self,evt):
        self.currentAxis.clear()
        for traceID,listener in self.listeners.items():
            if listener.axis == self.currentAxis:
                listener.unregister()
                del self.listeners[traceID]

    def onPlotParameters(self,evt):
        pass

    def onHelpAbout(self,evt):
        pass

    def OnPaint(self, evt):
        self.canvas.draw()

    def simReloaded(self):
        """Called by the simulation controller when the simulation is reloaded.

        Reregister all listeners, since they have been unregistered.
        """
        for listener in self.listeners.values():
            listener.reregister()
        
    # --------------------------------------------------------------------
    
    def newLayout(self):
        self.figure.clear()
        self.axes = []
	layoutCode = self.numRows*100 + self.numCols*10
        for row in range(self.numRows):
            for col in range(self.numCols):
                plotnum = row*self.numCols + col + 1
                axis=self.figure.add_subplot(layoutCode+plotnum)
                self.axes.append(axis)
        self.canvas.draw()
        for listener in self.listeners.values():
            listener.unregister()
        self.listeners={}
            

    def openTraceFile(self):
        dlg = wx.FileDialog(
            self, message="Choose a trace file",
            defaultDir=os.getcwd(), 
            defaultFile="",
            wildcard="All files (*.*)|*.*",
            style=wx.OPEN | wx.CHANGE_DIR)
        if dlg.ShowModal() != wx.ID_OK:
            return None
        filename = os.path.abspath(dlg.GetPaths()[0])
        try:
            traceFile=file(filename)
        except IOError,message:
            dlg = wx.MessageDialog(self, str(message),
                                   'File open error',
                                   wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return None
        return traceFile

    def newBarListenerDlg(self):
        dlg=self.res.LoadDialog(self, "barListenerDlg")
        wx.EVT_BUTTON(dlg,XRCID("button_OK_Listener"),
                   lambda evt: dlg.EndModal(wx.ID_OK))
        wx.EVT_BUTTON(dlg,XRCID("button_Cancel_Listener"),
                   lambda evt: dlg.EndModal(wx.ID_CANCEL))
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            traceID = XRCCTRL(dlg,"traceID").GetValue().strip()
            updateFreq = XRCCTRL(dlg,"listenerUpdates").GetValue()
            dlg.Destroy()
            if not traceID:
                errdlg = wx.MessageDialog(self, 'Invalid trace ID',
                                          'New bar plot listener',
                                          wx.OK | wx.ICON_ERROR)
                errdlg.ShowModal()
                errdlg.Destroy()
            else:
                return traceID,updateFreq

    def newLineListenerDlg(self):
        dlg=self.res.LoadDialog(self, "lineListenerDlg")
        wx.EVT_BUTTON(dlg,XRCID("button_OK_LineListener"),
                   lambda evt: dlg.EndModal(wx.ID_OK))
        wx.EVT_BUTTON(dlg,XRCID("button_Cancel_LineListener"),
                   lambda evt: dlg.EndModal(wx.ID_CANCEL))
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            traceID = XRCCTRL(dlg,"lineTraceID").GetValue().strip()
            updateFreq = XRCCTRL(dlg,"lineListenerUpdates").GetValue()
            visiblePoints = XRCCTRL(dlg,"lineVisiblePoints").GetValue()
            visiblePoints = visiblePoints.strip()
            if visiblePoints:
                try:
                    visiblePoints = int(visiblePoints)
                except ValueError:
                    visiblePoints = -1
            else:
                visiblePoints = 0
            keepInvisiblePoints = XRCCTRL(dlg,"lineKeepInvisiblePoints").GetValue()
            dlg.Destroy()
            if not traceID or visiblePoints < 0:
                if not traceID:
                    message = 'Invalid trace ID'
                elif visiblePoints < 0:
                    message = 'Invalid value for invisible points.' \
                              + 'Must be and integer or empty.'
                    
                errdlg = wx.MessageDialog(self, message,
                                          'New line plot listener',
                                          wx.OK | wx.ICON_ERROR)
                errdlg.ShowModal()
                errdlg.Destroy()
            else:
                return traceID,updateFreq,visiblePoints,keepInvisiblePoints

# ---------------------------------------------------------------------------

class BarListener(object):
    """Listens to trace values and updates the bar plot"""

    def __init__(self,traceID,axis,updateInterval):
        global canvas #@@@
        self.data = {}
        self.traceID = traceID
        self.axis = axis
        self.updateInterval = updateInterval
        self.lastUpdate = 0.0
        axis.clear()
        axis.set_title("Listener: %s"%traceID)
        canvas.draw() #@@@
        nessi.simulator.REGISTER_LISTENER(traceID,self.updatePlot)

    def updatePlot(self,simtime,traceID,value):
        """Receive trace values and update bar plot"""
        global canvas #@@@
        # The value is a string with the format: item1;item2;item3
        # where the items have the format: xvalue,yvalue
        value = value.strip()
        if value:
            items=value.split(';')
            for item in items:
                x,y=item.split(',')
                self.data[int(x)]=float(y)
        if time.time()-self.lastUpdate > self.updateInterval:
            xvec=self.data.keys()
            yvec=self.data.values()
            self.axis.clear()
            self.axis.bar(xvec,yvec)
            self.axis.set_title("Listener: %s"%traceID)
            canvas.draw()
            self.lastUpdate = time.time()

    def unregister(self):
        print "Unregistering"
        nessi.simulator.UNREGISTER_LISTENER(self.traceID,self.updatePlot)
        self.axis.clear()
        canvas.draw() #@@@

    def reregister(self):
        print "reregistering"
        nessi.simulator.REGISTER_LISTENER(self.traceID,self.updatePlot)        
        self.axis.clear()
        self.axis.set_title("Listener: %s"%self.traceID)
        canvas.draw() #@@@

class LineListener(object):
    """Listens to trace values and updates the line plot"""

    def __init__(self,traceID,axis,updateInterval,
                 visiblePoints,keepInvisiblePoints):
        global canvas #@@@
        self.traceID = traceID
        self.axis = axis
        self.updateInterval = updateInterval
        self.visiblePoints = visiblePoints
        self.keepInvisiblePoints = keepInvisiblePoints

        self.lastUpdate = 0.0
        self.nextUpdateIndex = 0
        self.data_x = array.array('d',[])
        self.data_y = array.array('d',[])
        axis.clear()
        axis.set_title("Listener: %s"%traceID)
        canvas.draw() #@@@
        nessi.simulator.REGISTER_LISTENER(traceID,self.updatePlot)

    def updatePlot(self,simtime,traceID,value):
        """Receive trace values and update line plot"""
        global canvas #@@@
        # The value is a single number or a sequence (x,y) of numbers
        if type(value) == float or type(value) == int:
            self.data_x.append(float(simtime))
            self.data_y.append(float(value))
        elif type(value) == list or type(value) == tuple:
            self.data_x.append(float(value[0]))
            self.data_y.append(float(value[1]))
            
        if time.time()-self.lastUpdate < self.updateInterval:
            return 

        # Redraw the plot
        if not self.keepInvisiblePoints:
            # Erase all old points
            numNewPoints = len(self.data_x) - self.nextUpdateIndex
            self.axis.clear()
            self.axis.set_title("Listener: %s"%self.traceID)
            self.data_x = self.data_x[-self.visiblePoints:]
            self.data_y = self.data_y[-self.visiblePoints:]
            self.nextUpdateIndex = 0

        xvec=self.data_x[self.nextUpdateIndex:]
        yvec=self.data_y[self.nextUpdateIndex:]
	try:
          self.axis.plot(xvec,yvec,'b')
	except ZeroDivisionError:
	  pass

        # Modify axes if the number of visible points is limited
        if self.visiblePoints:
            xvec = self.data_x[-self.visiblePoints:]
            minx = min(xvec); maxx = max(xvec)
            if maxx > minx: 
                self.axis.set_xlim((minx,maxx))
            yvec = self.data_y[-self.visiblePoints:]
            miny = min(yvec); maxy = max(yvec)
            if maxy > miny:
                self.axis.set_ylim((miny,maxy))
                
        canvas.draw()
        self.lastUpdate = time.time()
        self.nextUpdateIndex = max(0,len(self.data_x)-1)

    def unregister(self):
        print "Unregistering"
        nessi.simulator.UNREGISTER_LISTENER(self.traceID,self.updatePlot)
        self.axis.clear()
        canvas.draw() #@@@

    def reregister(self):
        print "reregistering"
        nessi.simulator.REGISTER_LISTENER(self.traceID,self.updatePlot)        
        self.axis.clear()
        self.axis.set_title("Listener: %s"%self.traceID)
        canvas.draw() #@@@

        
