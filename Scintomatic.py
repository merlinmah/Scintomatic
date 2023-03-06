#! /usr/bin/python3
"""
--------------------------------------------------------------------
Scintomatic
  by Merlin Mah and Mark Felice

A GUI to view and record data reported by the Hidex Triathler or Perkin Elmer BetaScout.


KNOWN ISSUES AND TODOS


DESIGN NOTES


SOURCES, REFERENCES, AND EXAMPLES REFERRED TO
- [https://stackoverflow.com/q/6783194] and [https://stackoverflow.com/q/6783194],
  which review the controversies and different recommended practices in Qt multithreading.
  This is a surprisingly contentious topic, with further examples to be found
  in a variety of places, e.g., [https://gist.github.com/jazzycamel/8abd37bf2d60cce6e01d].
- A table of latin-1 character encodings comes in handy for reading the spectrum bytearrays:
  [https://256stuff.com/gray/docs/latin.html]
- pyqtgraph offers better Qt integration and much more speed than our old standby matplotlib:
  [https://www.pythonguis.com/tutorials/pyside-plotting-pyqtgraph/]


MODIFICATION HISTORY
[ 2/16/2023] Finally added detection and GUI selection of serial ports.
[ 6/13/2022] Pruned a little vestigial code.
[ 4/17/2022] Simplified QRoundBar invocations and tweaked UI layout. 
             Fixed a few bugs derailing auto and manual data saving.
[ 3/14/2022] Now autosaves data by default. Disk is still cheap, right?
             Added support for the scintillator's using time units other than seconds.
             Found the missing spectrum byte, which was (is...) labeled interrupted.
             Swapped out print() statements for logging module.
             Bug fixes and UI tweaks by the truckload.
[ 3/10/2022] Merged in and streamlined fixes from live testing today.
[ 3/ 9/2022] Swapped out matplotlib (what PlotKit currently wraps) for the faster pyqtgraph.
[ 3/ 6/2022] Added spectrum bitsum checking.
[ 2/15/2022] A few cosmetic tweaks and a few untested program flow changes
[ 2/10/2022] Bug fixes en masse based on transcript playback testing.
[12/31/2021] First release approaches untested feature completion.
[12/29/2021] First field tests, resulting in major fixes to threading.
[12/24/2021] First version.

-------------------------------------------------------------------
"""

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets
from QtKit import FoldawaySplitter, QRoundBars, QToggleSwitches
import pyqtgraph

import sys
import os
import platform
import time
from datetime import datetime
import re
import queue

import InstrumentComm
import serial.tools.list_ports # For port detection [https://stackoverflow.com/a/52809180]
import scintillationcounters

import logging
logging.basicConfig(filename='Scintomatic.log', encoding='utf-8', level=logging.ERROR)


class PlotPanel(QtWidgets.QWidget):
    # QWidget GUI and some methods for displaying data, customizable downstream

    def __init__(self, parent):
        """
        Initializes a PlotPanel, a base class which can be customized for our various plots.
        """
        super(PlotPanel, self).__init__(parent=parent)

        # First, some declarations and defaults
        self.xdata = []
        self.ydata = []
        if os.path.isdir(os.path.join(os.getcwd(), 'Autosave')):
            self.autosaveDir = os.path.join(os.getcwd(), 'Autosave')
        else:
            self.autosaveDir = os.getcwd()

        # Set up UI
        self.mainLayout = QtWidgets.QHBoxLayout(self)

        # On the left, the main line plot
        self.lineplot = pyqtgraph.PlotWidget()
        self.lineplot.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.lineplot.updateGeometry()
        bgcolor = self.palette().color(QtGui.QPalette.Window) # Set plot background color to same as default window color
        self.lineplot.setBackground(bgcolor)
        textcolor = self.palette().color(QtGui.QPalette.WindowText) # [https://doc.qt.io/qtforpython-5/PySide2/QtGui/QPalette.html#PySide2.QtGui.PySide2.QtGui.QPalette.ColorRole]
        self.linepen = pyqtgraph.mkPen(color=(44, 160, 44), width=3) # For just lines, in matplotlib's default green color
        self.fillbrush = pyqtgraph.mkBrush(color=(44, 160, 44, 100)) # For filling in the area below lines; tuple is (r, g, b, a), all [0-255]
        self.axislabelstyles = {'color':textcolor, 'font-size':'14px'}

        # In a small right sidebar:
        self.rightbarLayout = QtWidgets.QVBoxLayout()

        # A ring to indicate progress of data transfers...
        self.progressRing = QRoundBars.QRoundBarAnimated(parent=self)
        self.progressRing.setSweep(0, 0)
        self.progressRing.setText(' ')
        self.progressRing.setSolidColor('#2ca02c')
        # self.progressRing.setContentsMargins(24, 0, 0, 0) # A dirty hack instead of figuring out why AlignHCenter isn't centering
        self.progressRing.customsize = (64, 64)
        roundringSizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.progressRing.setSizePolicy(roundringSizePolicy)
        
        # Package the ring with some status text to sort-of-explain it
        hlayout_ring = QtWidgets.QHBoxLayout()
        hlayout_ring.setContentsMargins(0, 0, 0, 0)
        self.progressLabel = QtWidgets.QLabel("", self)
        hlayout_ring.addWidget(self.progressRing, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        hlayout_ring.addWidget(self.progressLabel, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        self.rightbarLayout.addLayout(hlayout_ring, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        # A few datafields... (Both time-records and spectra have start and end times, although source/interpretation may differ)
        self.rightbarLayout.addItem(QtWidgets.QSpacerItem(5, 5, hData=QtWidgets.QSizePolicy.MinimumExpanding, vData=QtWidgets.QSizePolicy.Minimum)) # width, height, horizontal, vertical [https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QSpacerItem.html]
        label_protocolname = QtWidgets.QLabel('TYPE', self)
        self.rightbarLayout.addWidget(label_protocolname)
        self.protocolnameLabel = QtWidgets.QLabel("--", self)
        self.rightbarLayout.addWidget(self.protocolnameLabel)
        label_date = QtWidgets.QLabel('DATE', self)
        self.rightbarLayout.addWidget(label_date)
        self.dateLabel = QtWidgets.QLabel("--", self)
        self.rightbarLayout.addWidget(self.dateLabel)
        label_sample = QtWidgets.QLabel('SAMPLE #', self)
        self.rightbarLayout.addWidget(label_sample)
        self.samplenumberLabel = QtWidgets.QLabel("--", self)
        self.rightbarLayout.addWidget(self.samplenumberLabel)
        label_starttime = QtWidgets.QLabel('START TIME', self)
        # label_starttime.setStyleSheet("background-color:red;") # diagnostics
        self.rightbarLayout.addWidget(label_starttime)
        self.starttimeLabel = QtWidgets.QLabel("--", self)
        self.rightbarLayout.addWidget(self.starttimeLabel)
        # A blank widget for inheriting classes to easily customize...
        self.rightbarMissionModule = QtWidgets.QWidget(self)
        self.rightbarLayout.addWidget(self.rightbarMissionModule, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        # ...And at the bottom, controls for exporting data
        self.rightbarLayout.addStretch()
        autosaveLayout = QtWidgets.QHBoxLayout()
        self.autosaveSwitch = QToggleSwitches.QToggleSwitch()
        self.autosaveSwitch.setChecked(True)
        autosaveLayout.addWidget(self.autosaveSwitch, QtCore.Qt.AlignLeft | QtCore.Qt.AlignBottom)
        self.autosaveLabel = QtWidgets.QLabel('Autosave', self)
        self.autosaveLabel.setFont(QtGui.QFont('Arial', 10))
        autosaveLayout.addWidget(self.autosaveLabel, QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
        self.autosaveLabel.mousePressEvent = lambda mouseevent: self.setAutosaveDir() # The lambda wrapper serves to discard the mouse click event
        self.autosaveLabel.setToolTip("Automatically save this data to a time-stamped .txt file when the next recording begins, or upon Scintomatic exit. Click to set destination directory. Note it is never automatically purged!")
        
        self.rightbarLayout.addLayout(autosaveLayout, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
        self.saveButton = QtWidgets.QPushButton("Save data", self) # [http://doc.qt.io/qt-5/qpushbutton.html]
        self.saveButton.clicked.connect(PlotPanel.saveFile(self.saveData))
        self.rightbarLayout.addWidget(self.saveButton, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)

        # Cosmetic options for the labels above
        for fixedlabel in [label_protocolname, label_date, label_sample, label_starttime]:
            fixedlabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
            fixedlabel.setFont(QtGui.QFont('Arial', 10))
        for varlabel in [self.protocolnameLabel, self.dateLabel, self.samplenumberLabel, self.starttimeLabel]:
            varlabel.setFont(QtGui.QFont('Arial', 16))
            varlabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Finally, the panel layout
        self.mainLayout.addWidget(self.lineplot, stretch=9)
        self.mainLayout.addLayout(self.rightbarLayout, stretch=1)


    def reinit(self):
        """
        Blank all class-held data and re-initialize the plot.
        """
        self.xdata = []
        self.ydata = []
        self.lineplot.clear()
        self.plotline = self.lineplot.plot(self.xdata, self.ydata, pen=self.linepen) # Ahahahaaaaa
        self.progressRing.setSweep(0, 0)
        self.progressRing.setText(' ')

# DECORATORS

    def saveFile(savemethod):
        """
        A method, intended to be used as a decorator for a plot's savePDF (or other format) functions,
        which decorates a method with a "Save as" file selection UI wrapped around it.
        Note the absence of the usual class-reference 'self' argument, which cannot be used
        with the decorator itself. [http://stackoverflow.com/a/1263782]
        """
        def chooseandsave(self):
            destfilenames = QtWidgets.QFileDialog.getSaveFileName(None, 'Save to file...', './', '') # [https://www.tutorialspoint.com/pyqt/pyqt_qfiledialog_widget.htm]/[http://doc.qt.io/qt-5/qfiledialog.html]
            if len(destfilenames[0]) > 0:
                savemethod(destfilenames[0])
            else:
                return # User cancelled, so a tuple of null strings returned
        return chooseandsave


    def chooseDirectory(dirmethod):
        """
        Decorates a method with a "Choose directory" selection UI wrapped around it.
        Note the absence of the usual class-reference 'self' argument, which cannot be used
        with the decorator itself. [http://stackoverflow.com/a/1263782]
        """
        def choosedir(self):
            destdir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Choose directory...', './') # [https://www.tutorialspoint.com/pyqt/pyqt_qfiledialog_widget.htm]/[http://doc.qt.io/qt-5/qfiledialog.html]
            if len(destdir) > 0:
                dirmethod(self, destdir)
            else:
                return # User cancelled
        return choosedir


# SAVING

    @chooseDirectory
    def setAutosaveDir(self, destpath):
        """
        Sets the destination directory for autosaved data files.
        """
        self.autosaveDir = destpath


    @saveFile # [http://stackoverflow.com/a/1263782]
    def savePDF(self, destfilename):
        """
        When the "Save graph" button is clicked, hide any demo lines or annotations we've added,
        then save a PDF of the graph. (Getting the destination filename from the user is handled by decorator saveFile.)
        Code adapted from Orange: [https://github.com/biolab/orange-widget-base/blob/master/orangewidget/utils/PDFExporter.py]
        # TODO PROBABLY NOT WORKING - START AT THE self.getScene.render() COMMAND... OR DEL
        """
        pw = QtGui.QPdfWriter(destfilename)
        dpi = int(QtWidgets.QApplication.primaryScreen().logicalDotsPerInch())
        pw.setResolution(dpi)
        pw.setPageMargins(QMarginsF(0, 0, 0, 0))
        pw.setPageSize(QtGui.QPageSize(QtCore.QSizeF(self.getTargetRect().size()) / dpi * 25.4, QtGui.QPageSize.Millimeter))
        painter = QtGui.QPainter(pw)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if QtCore.QT_VERSION >= 0x050D00:
            painter.setRenderHint(QPainter.LosslessImageRendering, True)
        # render() the targeted plot (which is...?) using the QPdfWriter [https://stackoverflow.com/q/57286334]
        self.getScene().render(painter, QtCore.QRectF(self.getTargetRect()), QtCore.QRectF(self.getSourceRect()))
        painter.end()




class TimePanel(PlotPanel):
    # An heir of PlotPanel that specializes in plotting count rate vs. time

    def __init__(self, parent):
        super(TimePanel, self).__init__(parent)
        self.reinit()
        self.lineplot.setLabel('left', "Counts per minute", **self.axislabelstyles)
        self.lineplot.showGrid(x=True, y=True)


    def saveData(self, destfilename):
        """
        Generates a tab-separated text file containing the received data
        represented in the plot.
        """
        textFile = open(f"{destfilename}.txt", 'w') # Use 'a' if you want to append instead
        textFile.write("# Scintomatic \n")
        textFile.write("# Time count record \n")
        textFile.write(f"# Exported: {datetime.now().strftime('%H:%M:%S, %A, %b %d, %Y')} \n")
        textFile.write(f"# Measurement type: {self.protocolnameLabel.text()} \n")
        textFile.write(f"# Measurement date (Scintomatic time): {self.dateLabel.text()} \n")
        textFile.write(f"# Measurement sample number: {self.samplenumberLabel.text()} \n")
        textFile.write(f"# Measurement started (Scintomatic time): {self.starttimeLabel.text()} \n")
        textFile.write(f"# Notes:  \n") # Future use
        textFile.write("# \n")
        textFile.write("# \n")
        textFile.write("# \n")
        textFile.write(f"# Time (s)\tCounts (per minute)\n")
        for seconds, cpm in zip(self.xdata, self.ydata):
            textFile.write(f"{seconds}\t{cpm}\n")
        textFile.close()


    def autosave(self):
        """
        Invokes saveData() to save the current data. Intended to be used when a time data or spectra
        collection has concluded. Yes, these files will tend to pile up...
        """
        if self.autosaveSwitch.isChecked() and len(self.ydata) > 0:
            self.saveData(os.path.join(self.autosaveDir, f"{self.protocolnameLabel.text().strip(' ')}-{self.samplenumberLabel.text()} time - {datetime.now().strftime('%H-%M-%S, %Y%m%d')} Scintomatic AUTOSAVE"))


    def reinit(self):
        """
        Overridden from the parent class to support the scintillator's reporting time in units
        other than seconds.
        """
        super().reinit()
        self.lineplot.setLabel('bottom', "Time (sec)", **self.axislabelstyles)




class SpectrumPanel(PlotPanel):
    # An heir of PlotPanel that specializes in plotting channel spectra

    def __init__(self, parent):
        super(SpectrumPanel, self).__init__(parent)
        self.reinit()
        self.lineplot.setLabel('bottom', "Channel number", **self.axislabelstyles)
        self.lineplot.setLabel('left', "Counts", **self.axislabelstyles)
        self.lineplot.showGrid(x=True, y=True)


    def saveData(self, destfilename):
        """
        Generates a tab-separated text file containing the received data
        represented in the plot.
        """
        textFile = open(f"{destfilename}.txt", 'w') # Use 'a' if you want to append instead
        textFile.write("# Scintomatic \n")
        textFile.write("# Spectrum record \n")
        textFile.write(f"# Exported: {datetime.now().strftime('%H:%M:%S, %A, %b %d, %Y')} \n")
        textFile.write(f"# Measurement type: {self.protocolnameLabel.text()} \n")
        textFile.write(f"# Measurement date (instrument time): {self.dateLabel.text()} \n")
        textFile.write(f"# Measurement sample number: {self.samplenumberLabel.text()} \n")
        textFile.write(f"# Measurement started (instrument time): {self.starttimeLabel.text()} \n")
        textFile.write(f"# Notes:  \n") # Future use
        textFile.write("# \n")
        textFile.write("# \n")
        textFile.write("# Disclaimer: Data interpreted from an encoding protocol which was reverse-engineered without documentation or confirmation. No guarantee of correctness is given.\n")
        textFile.write(f"# Channel number\tCounts\n")
        for channel, counts in zip(self.xdata, self.ydata):
            textFile.write(f"{channel}\t{counts}\n")
        textFile.close()


    def autosave(self):
        """
        Invokes the saveData the current data. Intended to be used when a time data or spectra
        collection has concluded. Yes, these files will tend to pile up...
        """
        if self.autosaveSwitch.isChecked() and len(self.ydata) > 0:
            self.saveData(os.path.join(self.autosaveDir, f"{self.protocolnameLabel.text().strip(' ')}-{self.samplenumberLabel.text()} spectrum - {datetime.now().strftime('%H-%M-%S, %Y%m%d')} Scintomatic AUTOSAVE"))


    def reinit(self):
        """
        Overridden from the parent class to fill in the area between the line and 0.
        """
        super().reinit()
        self.lineplot.clear()
        self.plotline = self.lineplot.plot(self.xdata, self.ydata, pen=self.linepen, fillLevel=0, brush=self.fillbrush) # Ahahahaaaaa




# Worker-thread-to-be that monitors for new RS-232 traffic from the scintillation counter
class SerialHelper(QtCore.QObject):
    # Signals must be defined as part of the class prototype [https://stackoverflow.com/q/36559713]
    youvegotmail = QtCore.Signal()

    def __init__(self, scintillationcounter, serialinqueue, parent=None):
        super(SerialHelper, self).__init__(parent)
        self.scintcomm = scintillationcounter # A configured, active CommBasics-descended instance
        self.serialinqueue = serialinqueue # For relaying inbound serial traffic to the main thread
        logging.debug("Serial thread launched!") # diagnostics


    @QtCore.Slot()
    def checkSerial(self):
        """
        The parent SerialHelper QObject will be moved to a new Thread (by a moveToThread() call
        in the main Scintomatic thread) and assigned to run checkSerial(). 
        (See, this is why people want to subclass QThread...)
        """
        while not QtCore.QThread.currentThread().isInterruptionRequested():
            logging.debug("Serial thread checking for mail!")
            receivedbytes = self.scintcomm.read_until(b'\r')
            #receivedbytes = self.scintcomm.devcomm.read(1)
            logging.debug(f"Serial thread inbox ({len(receivedbytes)} bytes): '{receivedbytes}'\n") # diagnostics
            self.serialinqueue.put(receivedbytes)
            self.youvegotmail.emit()
            time.sleep(0.05)




# The main event!
class Scintomatic(QtWidgets.QWidget): # QMainWindow vs QWidget: [http://stackoverflow.com/q/18897695]

    def __init__(self):
        super(Scintomatic, self).__init__()

        # Use those inherited methods to tweak this new window
        self.resize(1200, 720)
        screeninfo = QtWidgets.QApplication.instance().primaryScreen().availableGeometry() # [https://stackoverflow.com/a/67629040]
        self.setMaximumSize(screeninfo.width(), screeninfo.height()) # Prevent window from growing (e.g. by child widgets) larger than the screen [http://stackoverflow.com/q/17893328]
        self.setMinimumSize(800, 600) # Seems to be needed to enforce maximum size
        self.move(int(screeninfo.center().x() - self.geometry().width()/2), int(screeninfo.center().y() - self.geometry().height()/2)) # Move window to center of screen [https://stackoverflow.com/a/42595040]
        self.setWindowTitle('Scint-o-matic')
        self.show()

        # Our UI, at least for now, is essentially two vertically-collapsible panels: one each for time and spectrum
        windowlayout = QtWidgets.QVBoxLayout(self)
        self.setLayout(windowlayout)

        self.vfoldaway = FoldawaySplitter.FoldawayVSplitter(self)
        self.vfoldaway.foldAnimation.setDuration(500)
        self.timepanel = TimePanel(self)
        self.spectrumpanel = SpectrumPanel(self)

        self.vfoldaway.addWidget(self.timepanel)
        self.vfoldaway.labelPanel(1, "Time")
        self.vfoldaway.addWidget(self.spectrumpanel)
        self.vfoldaway.labelPanel(2, "Spectrum")

        self.foldaway_time = 1 # Shortcut to the indexes of the panels in self.vfoldaway
        self.foldaway_spectrum = 2

        # Down at the bottom, a vertically-tiny fixed strip for serial thread controls
        serialstrip = QtWidgets.QWidget(self)
        serialstripLayout = QtWidgets.QHBoxLayout()
        serialstrip.setLayout(serialstripLayout)
        tinySizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        tinySizePolicy.setHorizontalStretch(1)
        tinySizePolicy.setVerticalStretch(1)
        self.serialSwitch = QToggleSwitches.QToggleSwitch(serialstrip)
        self.serialSwitch.setChecked(False)
        self.serialSwitch.clicked.connect(self.serialSwitch_responder)
        serialstripLayout.addWidget(self.serialSwitch, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        serialfixedlabel = QtWidgets.QLabel("<small>SERIAL</small>", self)
        serialfixedlabel.setSizePolicy(tinySizePolicy)
        serialstripLayout.addWidget(serialfixedlabel, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        
        # The middle of the serial strip swaps between traffic monitoring...
        self.serialStackedWidget = QtWidgets.QStackedWidget()
        self.serialLabel = QtWidgets.QLabel("<i>Set your scintillation counter to Commfil v.2 format, then click the </i><small>SERIAL</small> <i>switch to begin!</i>", self)
        serialLabelSizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)
        serialLabelSizePolicy.setHorizontalStretch(30)
        serialLabelSizePolicy.setVerticalStretch(1)
        self.serialLabel.setSizePolicy(serialLabelSizePolicy)
        self.serialStackedWidget.addWidget(self.serialLabel)
        
        # ...and, when serial connection is off, controls for choosing an RS-232 port
        self.commSelectWidget = QtWidgets.QWidget()
        commSelectLayout = QtWidgets.QHBoxLayout(self.commSelectWidget) # There's no QStackedWidget.addLayout, so "wrap" in a widget
        commLabel = QtWidgets.QLabel("<i>instrument on port</i>")
        commLabel.setSizePolicy(tinySizePolicy)
        commSelectLayout.addWidget(commLabel, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.commSelectCombobox = QtWidgets.QComboBox() # Populating this will be the job of self.refresh_comms()
        commSelectLayout.addWidget(self.commSelectCombobox, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.commRefreshButton = QtWidgets.QPushButton()
        self.commRefreshButton.setText('\u27f3') # At least on Ubuntu's Python 3.8...
        self.commRefreshButton.clicked.connect(self.refresh_comms)
        self.commRefreshButton.setMaximumSize(32, 32)
        commSelectLayout.addWidget(self.commRefreshButton, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        commSelectLayout.addSpacing(30)
        self.commSelectWidget.setSizePolicy(serialLabelSizePolicy)
        # self.commSelectWidget.setMaximumHeight(self.serialSwitch.height()) # TODO Reduces the extra height that appears/disappears, but doesn't eliminate it
        self.serialStackedWidget.addWidget(self.commSelectWidget)
        serialstripLayout.addWidget(self.serialStackedWidget, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        
        # Create a little hover button with QTooltip for basic 'About' info
        self.aboutButton = QtWidgets.QLabel("\u24d8", self)
        self.aboutButton.setSizePolicy(tinySizePolicy)
        QtWidgets.QToolTip.setFont(QtGui.QFont("Helvetica", 12))
        self.aboutButton.setToolTip("<b>Scintomatic</b><br />by Merlin Mah and Mark Felice.<br />github.com/merlinmah/Scintomatic")
        serialstripLayout.addWidget(self.aboutButton, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Pack it all into our vlayout
        windowlayout.addWidget(self.vfoldaway, stretch=30)
        windowlayout.addWidget(serialstrip, stretch=1)

        windowlayout.setContentsMargins(5, 5, 5, 5)
        windowlayout.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        # GUI up!
        self.show()
        self.vfoldaway.expand(self.foldaway_time)
        self.vfoldaway.collapse(self.foldaway_spectrum)

        # Pre-populate the serial choices box        
        self.refresh_comms()
        self.serialStackedWidget.setCurrentWidget(self.commSelectWidget)

        # Flags and regexes for interpreter()
        self.prevline = b''
        self.binaryblock = False        
        self.regex_protocolname_time = re.compile(b"Name\:\<([\ \-\w]*)\>([0-9]*)\ ([A-Za-z\.]*)([0-9]{4})") # Line before the "Start Time" one in a time preamble should contain the protocol name and the date
        self.regex_time = re.compile(b"\{t([\ 0-9]*)R\:([\ 0-9]*)") # During time readouts, one line gives time and CPM...
        self.regex_altline_time = re.compile(b"\[\<([\ \-\w]*)\>S\: *([0-9]*)") # ...alternating with another line giving protocol name and sample number
        self.regex_protocolname_spectrum = re.compile(b"\[([\ \-\w]*)\] *([0-9]*) ([A-Za-z\.]*)([0-9]{4,4})") # In a spectrum preamble, the line before the "Start Time" one should contain the protocol name and datestamp
        
        # Use a timer to trigger any cutesy UI effects we might want
        # self.interpretTimer = QtCore.QTimer()
        # self.interpretTimer.setTimerType(Qt.CoarseTimer)
        # self.interpretTimer.setInterval(200) # Could also use zero-millisecond timer, but that's on its way out [https://doc.qt.io/qtforpython-5/PySide2/QtCore/QTimer.html]
        # self.interpretTimer.timeout.connect(self.interpreter)

        # Finally, initialize some data flags
        self.prevtime = -1
        self.non_sec_mode = False
        self.bitsum = 0
        
        # For layout testing only
        # self.timepanel.progressLabel.setText("300")
        # self.spectrumpanel.progressLabel.setText("1024/1024")


    def refresh_comms(self):
        """
        Uses pyserial to inventory the system's serial ports [https://stackoverflow.com/a/52809180]
        and populate the commSelectCombobox.
        """
        allports = serial.tools.list_ports.comports() # Dict with each port's shortname as a key and full path as a value # TODO should probably be try-excepted for error message in GUI...
        self.portchoices = {f"{thisport.name}: {thisport.description}, {thisport.hwid}":str(thisport.device) for thisport in allports}
        self.commSelectCombobox.clear()
        self.commSelectCombobox.addItems(self.portchoices.keys())
    

    def serialSwitch_responder(self):
        """
        Activate or deactive serial communication and the helper thread that relays its traffic.
        """
        if self.serialSwitch.isChecked():
            try:
                self.scintcomm = scintillationcounters.Triathler(byte_formatting='latin-1')
                self.scintcomm.openRS232port(self.portchoices[self.commSelectCombobox.currentText()])
                self.scintcomm.devcomm.timeout = 2 # (sec) Allow read_until() calls to block long enough for a line terminator to almost certainly have arrived
                self.scintcomm.devcomm.write_timeout = 1 # (sec)
                self.scintcomm.devcomm.reset_input_buffer() # We make the somewhat dangerous assumption that the user doesn't want any data from before they hit the switch
                self.serialLabel.setText("<i>Serial connection established!</i>")
                self.serialStackedWidget.setCurrentWidget(self.serialLabel)
            except Exception as serialkiller:
                self.serialLabel.setText(f"<i><b>ERROR</b> {repr(serialkiller)[-55:]}</i>")
                self.serialSwitch.setChecked(False)
                raise serialkiller

            # Prepare a helper thread for serial communication [https://stackoverflow.com/a/33453124]
            self.serialinqueue = queue.Queue()
            # self.serialhelper = SerialHelper()
            self.serialhelper = SerialHelper(self.scintcomm, self.serialinqueue)
            self.serialthread = QtCore.QThread()
            self.serialhelper.youvegotmail.connect(self.interpreter) # Trigger our interpreter on the helper's signal
            self.serialhelper.moveToThread(self.serialthread)
            self.serialthread.started.connect(self.serialhelper.checkSerial) # Thread should start listening as soon as it launches
            self.serialthread.start() # Launches the thread
            self.serialLabel.setText("<i>Monitoring for serial traffic...</i>")
        else:
            self.serialLabel.setText("<i>Shutting down serial thread, give me a sec...</i>")
            try:
                self.serialthread.requestInterruption()
                self.serialthread.wait(2050)
                self.serialthread.quit()
                self.scintcomm.closeport()
            except AttributeError:
                logging.warning(f"[Scintomatic.serialSwitch_responder] no serial thread running to exit.")
            self.serialLabel.setText("<i>Off. Use the switch to the left to change that.</i>")
            self.serialStackedWidget.setCurrentWidget(self.commSelectWidget)


    #@QtCore.Slot()
    def interpreter(self):
        """
        Tries to make sense of what we receive via serial. Thanks to all the GUI update tasks this entails,
        this method must run in the primary thread (or we'd have to add a lot of queues.)

        CAUTION: much of this code is specific to the BetaScout/Triathler scintillation counters.
        Furthermore, it makes assumptions about how these devices behave based on
        only a few observations of their operations.
        """
        try:
            rawbytes = self.serialinqueue.get(block=False)
        except queue.Empty: # [https://docs.python.org/3/library/queue.html#queue.Queue.get]
            return False
        receivedbytes = rawbytes.strip(b'\n')
        # If serialthread's read timed out without receiving anything, we still get called
        if receivedbytes==b'':
            self.serialLabel.setText("<i>:: crickets ::</i>")
            return False
        else:
            displayline = self.scintcomm.tostring(receivedbytes).encode('unicode_escape').decode() # The 'unicode_escape' encoding double-backslashes the control sequences
            self.serialLabel.setText(displayline[0:64] + ('...' if len(displayline) > 64 else ''))
            
        # Check for known patterns
        if receivedbytes.startswith(b'Start Time '):
            # Start time of either a time readout or spectrum
            strparts = self.scintcomm.tostring(receivedbytes).split(":")
            starttimetext = f"{int(strparts[0][-2:]):02}:{int(strparts[1]):02}:{int(strparts[2]):02}"
            if self.prevline.startswith(b'[ '):
                # This is a spectrum's start time
                self.spectrumpanel.autosave()
                self.spectrumpanel.reinit()
                self.bitsum = 0
                self.vfoldaway.expand(self.foldaway_spectrum)
                if len(self.timepanel.ydata) > 0:
                    self.timepanel.progressRing.setSweep(0, 359) # Spectrum is usually preceded by a time run
                self.spectrumpanel.starttimeLabel.setText(starttimetext)
                (protocolname, dateDay, dateMonth, dateYear) = self.regex_protocolname_spectrum.findall(self.prevline)[0]
                self.spectrumpanel.protocolnameLabel.setText(self.scintcomm.tostring(protocolname))
                self.spectrumpanel.dateLabel.setText(f"{self.scintcomm.tostring(dateDay)} {self.scintcomm.tostring(dateMonth)} {self.scintcomm.tostring(dateYear)}")
            elif self.prevline.startswith(b'Name:< '):
                # This is a time readout's start time
                self.timepanel.autosave()
                self.timepanel.reinit()
                self.prevtime = -1
                self.non_sec_mode = False
                self.vfoldaway.expand(self.foldaway_time)
                self.vfoldaway.collapse(self.foldaway_spectrum) # Since the spectrum is now for the previous readout
                self.timepanel.starttimeLabel.setText(starttimetext)
                (protocolname, dateDay, dateMonth, dateYear) = self.regex_protocolname_time.findall(self.prevline)[0]
                self.timepanel.dateLabel.setText(f"{self.scintcomm.tostring(dateDay)} {self.scintcomm.tostring(dateMonth)} {self.scintcomm.tostring(dateYear)}")
        elif receivedbytes.startswith(b'{t '):
            # Time count in progress (only transmitted in Commfil v.2 mode, I believe!)
            (rawtime, counts) = self.regex_time.findall(receivedbytes)[0]
            if int(rawtime) < self.prevtime:
                # Time went backwards? We must have started a new sample and missed the preamble (granted, an edge case)
                self.timepanel.autosave()
                self.timepanel.reinit()
                self.vfoldaway.expand(self.foldaway_time)
                self.non_sec_mode = False
            elif int(rawtime)==self.prevtime: # The instrument gives one time update per second, no matter which units of time (seconds, minutes, etc.) it's using
                self.non_sec_mode = True
                self.timepanel.lineplot.setLabel('bottom', "Time (sec) (assuming one data point per sec)", **self.timepanel.axislabelstyles)
            self.timepanel.xdata.append(self.timepanel.xdata[-1]+1 if self.non_sec_mode else int(rawtime))
            self.timepanel.ydata.append(int(counts))
            self.timepanel.plotline.setData(self.timepanel.xdata, self.timepanel.ydata)
            # self.timepanel.lineplot.setXRange(0, self.timepanel.xdata[-1], padding=0)
            self.timepanel.progressRing.setSweep((self.timepanel.progressRing.beginAngle+29) % 360, (self.timepanel.progressRing.beginAngle+59) % 360) # We don't know total time, so just make the ring spin
            self.timepanel.progressRing.setText("\u22ef")
            self.timepanel.progressLabel.setText(f"{len(self.timepanel.ydata)} points")
            self.prevtime = int(rawtime)
            
            # The previous line should contain the protocol name; only sample #1 gets the full preamble, so we'll try to parse every one of these
            try:
                (protocolname, samplenumber) = self.regex_altline_time.findall(self.prevline)[0]
                self.timepanel.protocolnameLabel.setText(self.scintcomm.tostring(protocolname))
                # TODO reinit() if sampleNumber is not the same as the currently-displayed?
                self.timepanel.samplenumberLabel.setText(self.scintcomm.tostring(sampleNumber))
            except (IndexError, NameError) as e:
                logging.warning(f"Failed to find a protocol name and/or sample number in prev line '{self.prevline}' because: {repr(e)}")
        elif receivedbytes.startswith(b'=>Start(binary)'):
            # Start of a binary-encoded block, which is used for spectrum in Commfil v.2 mode
            self.binaryblock = True
            self.interrupted_bytechunk = b''
            self.spectrumpanel.progressRing.setSweep(0, 0)
            self.spectrumpanel.progressLabel.setText("0/1024")
        elif receivedbytes.startswith(b'=>End(binary)'):
            # End of a binary-encoded block, which is used for spectrum in Commfil v.2 mode
            self.binaryblock = False
            self.spectrumpanel.progressRing.setSweep(0, 359)
            # Clear out the queue of interrupted bytechunks, which we must have misidentified
            self.bytechunk_interpreter([self.interrupted_bytechunk]) # interrupted_bytechunk must be a single bytearray (which isn't a list) by the way we assign it
            if not len(self.spectrumpanel.ydata)==1024:
                self.spectrumpanel.progressRing.setText("\u2757")
                raise ScintomaticError(f"Crap, I have {len(self.spectrumpanel.ydata)} data points instead of 1024...")
        elif receivedbytes.startswith(b'Bitsum:'):
            theirbitsum = int(receivedbytes[7:])
            logging.info(f"Spectrum bitsum: instrument says {theirbitsum}, we have {self.bitsum}.") 
            if theirbitsum==self.bitsum:
                self.spectrumpanel.progressRing.setText("\u2713")
            else:
                self.spectrumpanel.progressRing.setText("\u2248")
                logging.warning(f"Spectrum bitsum mismatch: have {self.bitsum} vs transmitted {theirbitsum}.") # Known issue--bitsum hasn't been figured out
        elif self.binaryblock:
            """
            According to our reverse-engineering—the results of which have no authoritative confirmation!—
            the Triathler/BetaScout Commfil v.2 protocol encodes spectrum data (counts only)
            using a mini form of run-length encoding (RLE)[https://www.fileformat.info/mirror/egff/ch09_03.htm]
            only for the value 0. When the byte with decimal value 251 (=0xfb) is transmitted,
            the next byte will represent the number of consecutive 0s, from 1 to 251;
            if the run of 0s is longer than 251, a third 251 byte will signal the beginning of a fresh RLE run.
            All non-zero values are written out, each followed by a 255 (=0xff) byte;
            values larger than a single byte's (after reserved values) 250 capacity
            will be represented by two or more bytes, with little-endian byte order such that
            the least-significant byte (LSB) comes first and the most significant byte (MSB) appears last,
            to represent a base-250 number (evidenced by that decimal value not appearing in the data.)
            Byte values 252, 253, 254 are also reserved for the end-of-binary-block,
            the value 13, and the value 35, respectively.

            TL;DR the spectrum binary representation is composed of these byte combinations:

                (251 (=\xfb), number of consecutive repeats) for each runs of 0s numbering <= 251
                    Note the lack of a 255 delineator following.
                	Never occurs except after 255 (or another 251).
                	Its appearance means the next value will be a number of repetitions;
                        this can be followed without a 255 divider by the next non-zero value,
                        or by a 251 (the third consecutive) signalling the beginning of another batch of zeros.
                	Two consecutive 251s means literally 251 zeros.

                (value, 255 (=\xff)) for a single non-zero value < 250

                (LSB, [...,] MSB, 255) , in base-250, for a single non-zero value >= 250

                253 (=\xfd) is 13
                    Always appears where surrounding data strongly suggest 13, whereas \r does not occur within the binary blocks until paired with \n at the very end.
                	Since the latin-1 character set encodes this value as the carriage return \r, which is (part of) the instrument's line terminator, I suspect the substitution was made to avoid interrupting the serial transfer block.

                254 (\xfe) = 35
                    Always appears where 35 is plausible, whereas 35 doesn't appear anywhere.
                	The reason for this substitution is not clear to me.
                    It's also possible this is another encoding issue introduced somewhere in the readout serial stack.

                252 (=\xfc) denotes end of stream
                    Does not appear anywhere else.
            """
            logging.debug(f"Raw rawbytes (len {len(rawbytes)}): {rawbytes}\n  last 10 bytes '{rawbytes[-10:]}'")
            bytechunks = self.scintcomm.tobytes(rawbytes).split(b'\xff') # Split into chunks demarcated by the value divider
            logging.debug(f"Post-chunking rawbytes ({len(bytechunks)} chunks): {bytechunks} \n  last chunk: '{rawbytes[-1]}'")

            # First, figure out whether the last read_until() timed out in the middle of a chunk
            if not self.interrupted_bytechunk==b'':
                logging.debug(f"Interrupted bytechunk is present from last time.")
                if rawbytes[0:1]==b'\xff': # Note that slicing, not indexing, is necessary to not get an int [https://stackoverflow.com/q/28249597]
                    # The previous batch's last bytechunk was indeed ended. Add it to the front of the queue
                    bytechunks.insert(0, self.interrupted_bytechunk)
                    logging.debug(f"Added previous interrupted bytechunk to the front of the line, now {bytechunks}")
                elif rawbytes[0:1]==b'\xfc':
                    # Same thing, although edge case
                    bytechunks.insert(0, self.interrupted_bytechunk)
                    logging.debug(f"Added previous interrupted bytechunk (\xfc flag) to the front of the line, now {bytechunks}")
                else:
                    # The previous batch snipped its last chunk down the middle, and this is the other piece
                    bytechunks[0] = self.interrupted_bytechunk + bytechunks[0]
                    logging.debug(f"Added previous interrupted chunk half to the front of the line, now {bytechunks}")
            # Now, how about this read?
            if not (rawbytes[-1:]==b'\xff' or rawbytes[-1:]==b'\xfc'):
                # Our last current bytechunk wasn't ended for sure # TODO I suspect this is always triggering, but need to get confirmation
                logging.debug(f"Rawbytes ends with {rawbytes[-4:]}--last byte '{rawbytes[-1:]}'--which looks possibly interrupted... removing and storing last bytechunk '{bytechunks[-1]}'\n  bytechunks now {bytechunks}") # diagnostics
                self.interrupted_bytechunk = bytechunks[-1]
                bytechunks[-1] = b''
                logging.debug(f"  bytechunks now {bytechunks}") # diagnostics
            else:
                # Pretty sure the last bytechunk is whole
                logging.debug(f"Last 10 raw bytes were '{rawbytes[-10:]}', which looks complete. Clearing interrupted bytechunk (previously '{self.interrupted_bytechunk}').")
                self.interrupted_bytechunk = b''
            # Now we can process our list of bytechunks
            self.bytechunk_interpreter(bytechunks)
            self.spectrumpanel.progressRing.setSweep(0, int(359*len(self.spectrumpanel.ydata)/1024))
            # self.spectrumpanel.lineplot.setXRange(0, self.spectrumpanel.xdata[-1], padding=0)
            self.bitsum += sum([bin(rawbyte).count("1") for rawbyte in rawbytes]) # Eventually replace with Python 3.10's new faster int.bit_count() [https://stackoverflow.com/a/64848298] # TODO this may count read terminators... and is still waaaaay off
            logging.debug(f"ydata now {len(self.spectrumpanel.ydata)} values.")

        # The line before triggers often contains semi-useful information...
        self.prevline = receivedbytes


    def bytechunk_interpreter(self, bytechunks):
        """
        Takes a list of bytechunks--the binary stream from the instrument, split by
        the b'\xff' separator values--and outputs a list of decoded decimal values
        directly to the interface.
        (Undecided on the wisdom of having this function directly modify class-held storage arrays;
        it simplifies things a bit and avoids one additional structure to pass around, but it feels dangerous...)
        """
        logging.debug(f"bytechunk_interpreter processing {len(bytechunks)} bytechunks.") # diagnostics
        for chunkno, bytechunk in enumerate(bytechunks):
            try:
                decchunk = list(bytechunk) # Convert bytes into decimal values [0-255]
            except TypeError: # Means there's only one byte, which Python treats as an int
                    decchunk = [bytechunk]
            logging.debug(f"Bytechunk #{chunkno}: '{decchunk}'") # diagnostics
            if len(decchunk)==0:
                logging.debug(f" ...was empty. Skipping.") # diagnostics
                continue
            elif decchunk[0]==251:
                chunkindex = 0
                while chunkindex < len(decchunk):
                    if decchunk[chunkindex]==251: # Looks stupid, but I can't think of a cleverer yet safe way
                        self.spectrumpanel.ydata.extend([0]*self.byte_reconstructor([decchunk[chunkindex+1]])) # Extend vs append: [https://stackoverflow.com/a/252711]
                        logging.debug(f" -> added {self.byte_reconstructor([decchunk[chunkindex+1]])} 0s") # diagnostics
                        chunkindex += 2
                    elif decchunk[chunkindex]==252:
                        logging.debug(f" -> end of stream flag found: '{decchunk[chunkindex:]}'.") # diagnostics
                        break
                    else:
                        self.spectrumpanel.ydata.append(self.byte_reconstructor(decchunk[chunkindex:])) # A chunk can't contain more than one non-zero data value... probably famous last words
                        logging.debug(f" -> added {self.byte_reconstructor(decchunk[chunkindex:])} (after the 0 stretch)") # diagnostics
                        break # Data loss risk!
            else:
                self.spectrumpanel.ydata.append(self.byte_reconstructor(decchunk))
                logging.debug(f" -> added {self.byte_reconstructor(decchunk)}") # diagnostics
        self.spectrumpanel.xdata = range(0, len(self.spectrumpanel.ydata))
        self.spectrumpanel.plotline.setData(self.spectrumpanel.xdata, self.spectrumpanel.ydata)
        self.spectrumpanel.progressRing.setSweep(0, 360*float(len(self.spectrumpanel.ydata))/1024) # Not sure the event loop will ever get to show this anyway
        self.spectrumpanel.progressLabel.setText(f"{len(self.spectrumpanel.ydata)}/1024")


    def byte_reconstructor(self, LSB_to_MSB_dec_bytes):
        """
        Helper function that constructs a single decimal number from a list of bytes,
        each expressed as a decimal value, in reverse MSB/LSB order.
        Also takes care of the two special-case value substitutions.
        """
        translated_bytes = []
        for byte in LSB_to_MSB_dec_bytes:
            if byte==253:
                translated_bytes.append(13)
            elif byte==254:
                translated_bytes.append(35)
            elif byte==252: # With checks upstream, shouldn't be necessary... but we're leaving it in
                break # End of spectrum indicator
            else:
                translated_bytes.append(byte)
        translated_bytes = [byteval*(250**bytenum) for bytenum, byteval in enumerate(translated_bytes)]
        return sum(translated_bytes)


    def closeEvent(self, event):
        """
        Overrides the method triggered when the app is quit by clicking the OS window-close button
        in order to provide both possible threads a graceful exit. [https://stackoverflow.com/a/53102880]
        """
        self.serialLabel.setText("<i>Shutting down serial thread, give me a sec...</i>")
        try:
            self.serialthread.requestInterruption()
            self.serialthread.quit()
            self.serialthread.wait(2050) # (msec) without traffic, serialhelper takes about this long to notice
            self.scintcomm.closeport()
        except AttributeError:
            pass
        try:
            self.TimePanel.autosave()
            self.SpectrumPanel.autosave()
        except Exception:
            pass # Too late to do anything about it
        app.quit()



class ScintomaticError(InstrumentComm.Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(ScintomaticError, self).__init__('ScintOMatic', errorMessage, proxyerror)




if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    m = Scintomatic()
    operatingsystem = platform.system()
    sys.exit(app.exec())
