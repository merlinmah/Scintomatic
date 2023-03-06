#! /usr/bin/python3
"""
--------------------------------------------------------------------
QtKit.QRoundBar and QRoundBarAnimated
  by Merlin Mah

A progress bar that's been curved into a donut shape. 


KNOWN ISSUES AND TODOS



DESIGN NOTES



SOURCES, REFERENCES, AND EXAMPLES REFERRED TO
- QRoundBar was simplified from QRoundProgressBar, by Alexander Lutsenko [http://stackoverflow.com/a/33583019].


MODIFICATION HISTORY
[ 7/22/2022] Commented out the self.drawBackground() call to entirely eliminate the unnecessary backing square.
[ 4/19/2022] Tiny tweaks to support PySide6. 
[ 4/16/2022] Removed the "ringbearer" wrapper widget because it doesn't work, and isn't actually needed...
[ 3/16/2022] Integrated the "ringbearer" wrapper widget in QRoundBar.
[ 6/24/2021] Swapped from PyQt5 to the more flexibly-licensed and officially-supported PySide2 (Qt5).
			  As of this time, matplotlib does not support Qt6.
[11/ 2/2019] Added a custom QProperty, and thereby a mostly-transparent animation wrapper, to QRoundBar.
[ 1/15/2017] Spun off from REVEALer.py.

-------------------------------------------------------------------
"""

from PySide6 import QtCore, QtGui, QtWidgets
import logging
logging.basicConfig(level=logging.ERROR)



class QRoundBar(QtWidgets.QWidget):
	# Simplified from QRoundProgressBar by Alexander Lutsenko [http://stackoverflow.com/a/33583019]
	# See also [http://doc.qt.io/qt-5/qtwidgets-painting-basicdrawing-example.html]

	def __init__(self, parent=None):
		super(QRoundBar, self).__init__(parent=parent)
		self.twelveOClockIs = 0 # Which angle, in degrees, is at the top of the clock?
		self.beginAngle = -45 # Beginning of arc, in degrees
		self._endAngle = 45 # And similarly, the end. Note that negative is CCW; underscore reminds us that it's a custom QProperty
		self.text = ''

		self.barStyle = 'donut' # See self.drawBase() for the choices
		self.outlinePenWidth = 1
		self.dataPenWidth = 1
		self.rebuildBrush = True
		self.solidColor = '#FFFF0000' # Hex string, in ARGB format. Is set to None when using a gradient
		self.gradientData = [] # Is set to empty list when using a solid color
		self.donutThicknessRatio = 0.75
		self.customsize = (200, 200) # width, height

		# Attempt to ensure that neighboring rings stay the same size as each other [http://www.qtcentre.org/threads/9425-Forcing-two-widgets-to-the-same-size]
		self.sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
		self.sizePolicy.setHorizontalStretch(1) 
		self.sizePolicy.setVerticalStretch(1)
						
		# Other styling
		self.customBackground = None
		

	# Make endAngle a custom property
	def getEndAngle(self):
		return self._endAngle

	def setEndAngle(self, newval):
		self._endAngle = newval
		self.update() # Important: the key to the animation actually playing! [https://www.qtcentre.org/threads/59418-QPropertyAnimation-does-not-redraw-the-object]

	endAngle = QtCore.Property(float, getEndAngle, setEndAngle)

	def setText(self, text):
		self.text = text
		self.update()

	def getSweep(self):
		return (self.beginAngle, self._endAngle)

	def setSweep(self, beginAngle, endAngle):
		self.beginAngle = beginAngle
		# self.endAngle = QtCore.QVariant(endAngle) # QVariant's .setValue() doesn't seem to be in PyQt5
		self.setEndAngle(endAngle)
		if self.solidColor==None:
			self.rebuildBrush = True
		self.update()

	def setOutlinePenWidth(self, penWidth):
		self.outlinePenWidth = penWidth
		self.update()

	def setDataPenWidth(self, penWidth):
		self.dataPenWidth = penWidth
		self.update()

	def setGradientColors(self, stopPoints):
		self.gradientData = stopPoints
		self.solidcolor = None
		self.rebuildBrush = True
		self.update()

	def setSolidColor(self, hexARGB):
		self.solidColor = hexARGB
		self.gradientData = []
		self.rebuildBrush = True
		self.update()

	def setDonutThicknessRatio(self, val):
		self.donutThicknessRatio = max(0., min(val, 1.))
		self.update()

	def sizeHint(self):
		"""
		Apparently necessary to make this QWidget behave with alignments.
		[http://stackoverflow.com/a/20468193]
		"""
		return QtCore.QSize(self.customsize[0], self.customsize[1])

	def paintEvent(self, event):
		"""
		The method called to actually do the drawing
		"""
		outerRadius = min(self.width(), self.height())
		baseRect = QtCore.QRectF(1, 1, outerRadius-2, outerRadius-2)

		buffer = QtGui.QImage(outerRadius, outerRadius, QtGui.QImage.Format_ARGB32)
		buffer.fill(0)

		p = QtGui.QPainter(buffer)
		p.setRenderHint(QtGui.QPainter.Antialiasing)

		self.rebuildDataBrushIfNeeded()
		# self.drawBackground(p, buffer.rect()) # Background
		self.drawBase(p, baseRect) # The base circle
		self.drawRing(p, baseRect, self.beginAngle, self.getEndAngle()) # The variably-sized data arc
		innerRect, innerRadius = self.calculateInnerRect(baseRect, outerRadius)
		self.drawInnerBackground(p, innerRect) # The inner circle which makes the thing look like a donut/ring
		self.drawText(p, innerRect, innerRadius, self.text)

		p.end() # Voila!

		painter = QtGui.QPainter(self)
		painter.drawImage(0, 0, buffer)

	def drawBackground(self, p, baseRect):
		if self.customBackground==None:
			p.fillRect(baseRect, self.palette().window())
		else:
			p.fillRect(baseRect, QtGui.QColor(self.customBackground))

	def drawBase(self, p, baseRect):
		if self.barStyle == 'donut':
			p.setPen(QtGui.QPen(self.palette().shadow().color(), self.outlinePenWidth))
			p.setBrush(self.palette().base())
			p.drawEllipse(baseRect)
		elif self.barStyle == 'pie':
			p.setPen(QtGui.QPen(self.palette().base().color(), self.outlinePenWidth))
			p.setBrush(self.palette().base())
			p.drawEllipse(baseRect)
		elif self.barStyle == 'line':
			p.setPen(QtGui.QPen(self.palette().base().color(), self.outlinePenWidth))
			p.setBrush(QtCore.Qt.NoBrush)
			p.drawEllipse(baseRect.adjusted(self.outlinePenWidth/2, self.outlinePenWidth/2, -self.outlinePenWidth/2, -self.outlinePenWidth/2))
		else:
			logging.error("ERROR [QRoundProgressBar.drawBase]: style string {} not known!".format(baseRect))

	def drawRing(self, p, baseRect, beginAngle, endAngle):
		"""
		Given angles in degrees beginAngle and endAngle, draws the appropriate circular arc.
		Note while the Qt5 QPainter.drawArc() documentation [http://doc.qt.io/qt-5/qpainter.html#drawArc]
		claims that it requires an integer number of 1/16 degree segments, 0 degrees is at 3 o'clock,
		and positive angles are in the CCW direction, the only one of these that bears out experimentally is
		the default origin being at the eastern compass point.
		"""
		startOffset = 90 + int(self.twelveOClockIs)
		startAngle = startOffset - int(round(beginAngle))
		spanAngle = int(round(endAngle - beginAngle))
		# logging.debug("beginAngle: {}  endAngle: {}  startAngle: {}  spanAngle: {}".format(beginAngle, endAngle, startAngle, spanAngle)) # diagnostics
		if self.barStyle == 'line':
			p.setPen(QtGui.QPen(self.palette().highlight().color(), self.dataPenWidth))
			p.setBrush(QtCore.Qt.NoBrush)
			p.drawArc(baseRect.adjusted(self.outlinePenWidth/2, self.outlinePenWidth/2, -self.outlinePenWidth/2, -self.outlinePenWidth/2),
					  startAngle=startAngle, spanAngle=spanAngle) # [http://doc.qt.io/qt-5/qpainter.html#drawArc]
			return

		# for Pie and Donut styles
		dataPath = QtGui.QPainterPath()
		dataPath.setFillRule(QtCore.Qt.WindingFill) # [http://doc.qt.io/qt-4.8/qt.html#FillRule-enum]

		# pie segment outer
		dataPath.moveTo(baseRect.center())
		dataPath.arcTo(baseRect, startAngle, -spanAngle)
		dataPath.lineTo(baseRect.center())

		p.setBrush(self.palette().highlight())
		p.setPen(QtGui.QPen(self.palette().shadow().color(), self.dataPenWidth))
		p.drawPath(dataPath)

	def calculateInnerRect(self, baseRect, outerRadius):
		if self.barStyle == 'line':
			innerRadius = outerRadius - self.outlinePenWidth
		else:
			innerRadius = outerRadius * self.donutThicknessRatio

		delta = (outerRadius - innerRadius) / 2.
		innerRect = QtCore.QRectF(delta, delta, innerRadius, innerRadius)
		return innerRect, innerRadius

	def drawInnerBackground(self, p, innerRect):
		if self.barStyle == 'donut':
			p.setBrush(self.palette().alternateBase())
			cmod = p.compositionMode()
			p.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
			p.drawEllipse(innerRect)
			p.setCompositionMode(cmod)

	def drawText(self, p, innerRect, innerRadius, text):
		f = self.font()
		f.setPixelSize(innerRadius * 1.2 / max(len(text), 1)) # [http://doc.qt.io/qt-5/qfont.html]
		p.setFont(f)

		textRect = innerRect
		p.setPen(self.palette().text().color())
		p.drawText(textRect, QtCore.Qt.AlignCenter, text) # [http://doc.qt.io/qt-5/qpainter.html#drawText-4]


	def rebuildDataBrushIfNeeded(self):
		if not self.rebuildBrush:
			return
		else:
			self.rebuildBrush = False
			if self.gradientData:
				dataBrush = QtGui.QConicalGradient() # [http://doc.qt.io/qt-5/qbrush.html]
				dataBrush.setCenter(0.5, 0.5)
				dataBrush.setCoordinateMode(QtGui.QGradient.StretchToDeviceMode)

				for pos, color in self.gradientData:
					dataBrush.setColorAt(1.0 - pos, color)

				dataBrush.setAngle(self.beginAngle)
			else:
				dataBrush = QtGui.QBrush(QtGui.QColor(self.solidColor))
				dataBrush.setStyle(QtCore.Qt.SolidPattern) # [http://doc.qt.io/qt-5/qcolor.html#details]
			p = self.palette()
			p.setBrush(QtGui.QPalette.Highlight, dataBrush)
			self.setPalette(p)




class QRoundBarAnimated(QRoundBar, QtWidgets.QWidget):
	# A nearly-transparent wrapper of QRoundBar which uses QPropertyAnimation to animate the ring sweep.

	def __init__(self, parent=None):
		super(QRoundBarAnimated, self).__init__(parent=parent)
		self.sweepanimation = QtCore.QPropertyAnimation(self, b"endAngle")
		self.sweepanimation.setDuration(100)
		self.sweepanimation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
		self.setUpdatesEnabled(True) # [https://forum.qt.io/topic/81047/is-it-possible-to-freeze-qwidget-during-qpropertyanimation-works/6] but nope
		self.setSweep(0, 0)
		# self.update()


	def setSweep(self, beginAngle, endAngle):
		"""
		Since this is the method most commonly used to set the endAngle of a QRoundBar,
		override it to trigger the endAngle sweep animation.
		"""
		# First, most of the things that QRoundBar.setSweep() does
		self.beginAngle = beginAngle
		if self.solidColor==None:
			self.rebuildBrush = True

		# Now we can add the sweep animation
		# Generates warnings if you don't recreate every time, but eh for now
		# self.sweepanimation = QtCore.QPropertyAnimation(self, b"endAngle")
		# self.sweepanimation.setDuration(500)
		# self.setUpdatesEnabled(True) # [https://forum.qt.io/topic/81047/is-it-possible-to-freeze-qwidget-during-qpropertyanimation-works/6] but nope
		# self.sweepanimation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
		self.sweepanimation.setStartValue(self.getEndAngle())
		self.sweepanimation.setEndValue(endAngle)
		self.sweepanimation.start()

