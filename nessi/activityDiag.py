# Nessi Network Simulator
#                                                                        
# Authors:  Juergen Ehrensberger (HEIG-VD)
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

"""Activity Diagram."""

if __name__ == '__main__':
    import wx
    from wx.xrc import *

class ActivityManager(object):
    """Manages activities of all actors."""

    def __init__(self):
        self._actors = {}
        self._currentEvent = {}

    def newActivity(self, time, actor, text, graphic):
        if actor not in self._actors:
            if graphic == 'last':
                raise ValueError("First activity can't have 'last' as graphic")
            self._actors[actor] = [(time, text, graphic)]
            self._currentEvent[actor] = 0
        else:
            if graphic == 'last':
                graphic = self._actors[actor][-1][2]
        self._actors[actor].append((time, text, graphic))

    def actors(self):
        actorlist = self._actors.keys()
        actorlist.sort()
        return actorlist

    def resetIter(self, actor):
        """Reset the iterator to the first event of the actor."""
        self._currentEvent[actor] = 0

    def currentEvent(self, actor):
        """Return the current event of the iterator of the actor."""
        return self._actors[actor][self._currentEvent[actor]]

    def nextEvent(self, actor):
        """Return the next event of the actor or raise StopIteration."""
        index = self._currentEvent[actor] + 1
        try:
            event = self._actors[actor][index]
        except IndexError:
            raise StopIteration
        self._currentEvent[actor] = index
        return event
    
    def events(self, actor):
        activities = self._actors[actor]
        return self._actors[actor]

    def maxTime(self, actor):
        return self._actors[actor][-1][0]

    def minTime(self, actor):
        return self._actors[actor][0][0]

class StyleManager(object):
    """Manages drawing parameters and resources for layout."""
    
    styles = [wx.SOLID, wx.BDIAGONAL_HATCH, wx.CROSSDIAG_HATCH,
             wx.FDIAGONAL_HATCH, wx.CROSS_HATCH, wx.HORIZONTAL_HATCH,
             wx.VERTICAL_HATCH]
    
    def __init__(self):
        # Layout parameters
        self.pixPerSec = 'auto'
        self.pixPerActor = 60
        self.headerSpace = 0
        self.leftBorder = 'auto'
        self.rightBorder = 0

        # General style
        self.background = wx.NamedColour("white")
        self.backgroundBrush = wx.Brush(self.background, wx.SOLID)

        # Style for actor names
        self.actorFont = wx.Font(12, wx.SWISS, wx.NORMAL,
                                   wx.NORMAL,False,"Arial")
        self.actorForeground = wx.NamedColour("black")

        # Axis style
        self.axisYPos = 20
        self.axisPen = wx.Pen(wx.NamedColour("black"), 1, wx.SOLID)
        self.axisFont = wx.Font(12, wx.SWISS, wx.NORMAL,
                                  wx.NORMAL,False,"Arial")

        # Style for time labels on the axis
        self.timeTickLength = 5
        self.timeForeground = wx.NamedColour("black")
        self.timeFont = wx.Font(12, wx.SWISS, wx.NORMAL,
                                  wx.NORMAL,False,"Arial")
        self.timePos = self.axisYPos-self.timeTickLength
        self.timePen = wx.Pen(wx.NamedColour("black"), 1, wx.SOLID)
        self.showTimes = True

        # Style for graphics
        self.graphicSize = 18

        # Style for event texts and start markers
        self.textFont = wx.Font(12, wx.SWISS, wx.NORMAL,
                                  wx.NORMAL,False,"Arial")
        self.textForeground = wx.NamedColour("black")
        self.textPos = self.graphicSize+self.axisYPos+self.textHeight(self.textFont)
        self.textMarkerPos = self.graphicSize+self.axisYPos+1
        self.textMarkerSize = 6
        self.textMarkerPen = wx.Pen(wx.NamedColour("black"), 1, wx.SOLID)
        self.showTexts = True

    def textHeight(self, font):
        bmp = wx.EmptyBitmap(100,100)
        dc = wx.MemoryDC()
        dc.SelectObject(bmp)
        dc.SetFont(font)
        width, height = dc.GetTextExtent("A")
        return height
        
    def graphic(self, graphic):
        """Return the width, a pen and a brush to draw this graphic."""
        color, size, style = graphic
        color = wx.NamedColour(color)
        thickness = self.graphicSize / (1<<size)
        yOffset = (self.graphicSize-thickness) / 2
        pen = wx.Pen(color, 1, wx.SOLID)
        brush = wx.Brush(color, self.styles[style])
        return thickness, yOffset, pen, brush
        
    
class DrawManager(object):
    """Manages the layout and drawing of activities on the canvas."""

    def __init__(self, activities, canvas):
        self.activities = activities
        self.canvas = canvas
        self.styleManager = StyleManager()
        self._diagram = wx.EmptyBitmap(100,100)
        self.clearBitmap(self._diagram)

    def clearBitmap(self, bmp):
        dc = wx.MemoryDC()
        dc.SelectObject(bmp)
        brush = self.styleManager.backgroundBrush
        dc.SetBackground(brush)
        dc.Clear()
       
    def layout(self):
        """Determine the pixels per second and min and max times."""
        actors = self.activities.actors()
        # Determine the number of pixels per second, such that
        # there are on average 100 pixels per event
        minTime = 1L<<32
        maxTime = 0
        pixPerSec = 1
        for actor in actors:
            actorMaxTime = self.activities.maxTime(actor)
            actorMinTime = self.activities.minTime(actor)
            minTime = min(minTime, actorMinTime)
            maxTime = max(maxTime, actorMaxTime)
            actorTime = actorMaxTime - actorMinTime
            numEvents = len(self.activities.events(actor))
            if actorTime > 0:
                pixPerSec = max(pixPerSec, 100 * numEvents / actorTime)

        if self.styleManager.pixPerSec != 'auto':
            pixPerSec = self.styleManager.pixPerSec

        # Determine the size of the left border
        if  self.styleManager.leftBorder != 'auto':
            leftBorder = self.styleManager.leftBorder
        else:
            bmp = wx.EmptyBitmap(100,100)
            dc = wx.MemoryDC()
            dc.SelectObject(bmp)
            dc.SetFont(self.styleManager.actorFont)
            dc.SetTextForeground(self.styleManager.actorForeground)
            leftBorder = 1
            for actor in actors:
                leftBorder = max(leftBorder, dc.GetTextExtent(actor)[0])

        self._pixPerSec = pixPerSec
        self._minTime = minTime
        self._maxTime = maxTime 
        self._leftBorder = leftBorder
        self._rightBorder = self.styleManager.rightBorder
                    
    def drawAll(self, dc=None):
        """Redraw the whole diagramm.

        Used for drawing the first time or after a style update.
        """
        actors = self.activities.actors()
        self.layout()
        width = ( (self._maxTime-self._minTime) * self._pixPerSec
                  + self._leftBorder + self._rightBorder)
        pixPerActor = self.styleManager.pixPerActor
        height = max(1, pixPerActor * len(actors))

        # First draw events, times and texts bitmap separately for each actor
        self._actorDiagrams = {}
        for actor in actors:
            eventsBmp = wx.EmptyBitmap(width, pixPerActor)
            self.clearBitmap(eventsBmp)
            timesBmp = wx.EmptyBitmap(width, pixPerActor)
            self.clearBitmap(timesBmp)
            textsBmp = wx.EmptyBitmap(width, pixPerActor)
            self.clearBitmap(textsBmp)
            self._actorDiagrams[actor] = (eventsBmp, timesBmp, textsBmp)

            self.activities.resetIter(actor)
            while self.drawEvent(actor):
                pass

        # Now copy the different bitmaps into the main diagram
        self._diagram = wx.EmptyBitmap(width, height)
        self.clearBitmap(self._diagram)
        yOffset = self.styleManager.headerSpace
        dc = wx.MemoryDC()
        dc.SelectObject(self._diagram)
        dc.Clear()
        for actor in actors:
            eventsBmp, timesBmp, textsBmp = self._actorDiagrams[actor]
            tmpDC = wx.MemoryDC()
            tmpDC.SelectObject(eventsBmp)
            dc.Blit(xdest=0, ydest=yOffset, width=width, height=pixPerActor,
                    source=tmpDC, xsrc=0, ysrc=0)

            if self.styleManager.showTexts == True:
                tmpDC = wx.MemoryDC()
                tmpDC.SelectObject(textsBmp)
                dc.Blit(xdest=0, ydest=yOffset, width=width,
                        height=pixPerActor, source=tmpDC, xsrc=0, ysrc=0,
                        rop=wx.AND)
                
            if self.styleManager.showTimes == True:
                tmpDC = wx.MemoryDC()
                tmpDC.SelectObject(timesBmp)
                dc.Blit(xdest=0, ydest=yOffset, width=width,
                        height=pixPerActor, source=tmpDC, xsrc=0, ysrc=0,
                        rop=wx.AND)
                
            yOffset += pixPerActor

        self.canvas.drawBitmap(self._diagram)

    def drawEvent(self, actor):
        """Draw a single new events with graphic, text, time."""
        try:
            self.count += 1
        except Exception:
            self.count=0
        print self.count
        
        currTime, currText, currGraphic = self.activities.currentEvent(actor)
        try:
            nextTime, nextText, nextGraphic = self.activities.nextEvent(actor)
        except StopIteration:
            return False # Indicate the draw did not succeed

        eventsBmp, timesBmp, textsBmp = self._actorDiagrams[actor]
        xStart = (currTime-self._minTime) * self._pixPerSec + self._leftBorder
        xEnd = (nextTime-self._minTime) * self._pixPerSec + self._leftBorder
        height = self.styleManager.pixPerActor
        
        # Extend the axis and draw the graphic 
        eventsBmp.SetWidth(xEnd) 
        dc = wx.MemoryDC()
        dc.SelectObject(eventsBmp)
        dc.CalcBoundingBox(xEnd, height)
        y = self.styleManager.axisYPos
        if currGraphic != None:
            thickness, yOffset, pen, brush = self.styleManager.graphic(currGraphic)
            dc.SetPen(pen)
            dc.SetBrush(brush)
            dc.DrawRectangle(xStart, height-(y+yOffset+thickness), xEnd-xStart, thickness)
        dc.SetPen(self.styleManager.axisPen)
        dc.DrawLine(xStart, height-y, xEnd, height-y)

        # Draw the text
        swapper = 6
        swapmiddle = swapper/2
        if len(currText) > 0:
            dc = wx.MemoryDC()
            dc.SelectObject(textsBmp)
            dc.SetPen(self.styleManager.textMarkerPen)
            delta = self.styleManager.textMarkerSize
            dc.SetFont(self.styleManager.textFont)
            dc.SetTextForeground(self.styleManager.textForeground)
            dc.SetTextBackground(self.styleManager.background)
            dc.SetBackgroundMode(wx.SOLID)
            y = self.styleManager.textPos
            dc.DrawText("   "+currText, xStart-delta, height-y-swapmiddle+swapper)
            y = self.styleManager.textMarkerPos
            dc.DrawPolygon([(0,0),(delta/2,-delta),(-delta/2,-delta),(0,0)],
                           xStart, height-y-swapmiddle+swapper)
            swapper = -swapper

            # Draw the time label on the axis
            dc = wx.MemoryDC()
            dc.SelectObject(timesBmp)
            dc.SetFont(self.styleManager.timeFont)
            dc.SetTextForeground(self.styleManager.timeForeground)
            dc.SetTextBackground(self.styleManager.background)
            dc.SetBackgroundMode(wx.SOLID)
            y = self.styleManager.timePos
            dc.DrawText("%0.3f"%currTime, xStart, height-y)

            dc.SetPen(self.styleManager.timePen)
            y = self.styleManager.axisYPos
            length = self.styleManager.timeTickLength
            dc.DrawLine(xStart, height-y, xStart, height-(y-length))
        return True


class Canvas(wx.Window):
    """Decorated plot window accepting draw commands"""

    def __init__(self, parent=None, id=-1,title='Activity Diagram'):
        """Create a parent frame and decorate self with scrollbars."""

        # Initialize instance variables
        self.size = (1000,1000)
        self.background_color = "white"

        self._bitmap = None

        # Create scrolledwin to decorate the canvas
        self.parentWin = wx.ScrolledWindow(parent,-1,wx.DefaultPosition,
                                          wx.DefaultSize)
        self.parentWin.SetScrollRate(1,1)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.parentWin.SetSizer(self.sizer)

        wx.Window.__init__(self, self.parentWin, -1, wx.DefaultPosition,
                             self.size)
        background = wx.NamedColour(self.background_color)
        self.SetBackgroundColour(background) 
        self.sizer.Add(self, 0, 0, 0)

        wx.EVT_PAINT(self,self.on_paint)
        wx.EVT_SIZE(self, self.on_size)

    def drawBitmap(self, bitmap):
        self._bitmap = bitmap
        width, height = bitmap.GetWidth(), bitmap.GetHeight()
        #self.SetSize((width, height))
        self.sizer.SetItemMinSize(self, width, height)
        
    def on_paint(self, event):
        if self._bitmap == None:
            return
        dc = wx.PaintDC(self)
        dc.DrawBitmap(self._bitmap, 0, 0)
        
    def on_size(self, event):
        pass


class ActivityDiagram(wx.App):
    """Stand-along GUI responsible for menu bars and accepting activities."""

    frame_size = (500,250)
    
    def OnInit(self):
        self.res = XmlResource("activityDiag.xrc")
        self.frame = self.res.LoadFrame(None, "mainframe")
        self.toolbar = XRCCTRL(self.frame, "toolbar")
        self.statusbar = XRCCTRL(self.frame, "statusbar")
        wx.EVT_MENU(self.frame, XRCID("file_open"), self.onFileOpen)
        wx.EVT_MENU(self.frame, XRCID("file_close"), self.onFileClose)
        wx.EVT_MENU(self.frame, XRCID("file_exit"), self.onFileExit)
        wx.EVT_MENU(self.frame, XRCID("help_about"), self.onHelpAbout)
        wx.EVT_MENU(self.frame, XRCID("tool_open"), self.onFileOpen)

        self.canvas = Canvas(self.frame)
        self.frame.Show(1)
        self.SetTopWindow(self.frame)

        self.activities = ActivityManager()
        self.drawManager = DrawManager(self.activities, self.canvas)
        return True

    # ---------------------------------------------------------------

    def onFileOpen(self, evt):
        dialog = wx.FileDialog(self.frame, "Activity trace file to read")
        ret = dialog.ShowModal()
        if ret == wx.ID_OK:
            filename = dialog.GetPath()
        self.readActivityTrace(filename)

    def onFileClose(self,evt):
        pass

    def onFileExit(self,evt):
        pass

    def onHelpAbout(self,evt):
        pass

    # ---------------------------------------------------------------

    def readActivityTrace(self, filename):
        file = open(filename)
        for line in file:
            time = line.split()[0]
            actor,text,graphic = line.replace(time,"",1).strip().split('#')
            time = float(time)
            if len(graphic) == 0:
                graphic = None
            elif graphic != 'last':
                color, size, style = graphic.split(',')
                size = int(size)
                style = int(style)
                graphic = (color, size, style)
            self.activities.newActivity(time, actor, text, graphic)

        self.drawManager.drawAll()
        
if __name__ == '__main__':
    diagram = ActivityDiagram(0)
    diagram.MainLoop()
    
#     import threading
#     import random
#     diag = ActivityDiagram(0)
#     guitr = threading.Thread(target=diag.MainLoop)
#     guitr.start()

#     # Draw something
#     activities = ["carrierSense", "Backoff", "deferring", "send", "receive",
#                   "COLLISION"]
#     colors = ['blue','green','red','yellow','orange', 'grey','light grey']

#     time = 0.0
#     for i in range(1000):
#         time += random.random()
#         node = "host_%d"%int(random.random()*10)
#         text = activities[int(random.random()*len(activities))]

#         if random.random() > 0.4:
#             style = 0#int(random.random()*7)
#             color = colors[int(random.random()*len(colors))]
#             weight = int(random.random()*3)
#             graphic = (color, weight, style)
#         else:
#             graphic = None
#         diag.activity(time, node, text, graphic)
#     print time
#     diag.drawManager.drawAll()
