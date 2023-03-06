#! /usr/bin/python3
"""
--------------------------------------------------------------------
QtKit.QToggleSwitch (and derivatives)
  by Merlin Mah

An iOS-style toggle switch, something Qt perplexingly omitted.


KNOWN ISSUES AND TODOS



DESIGN NOTES



SOURCES, REFERENCES, AND EXAMPLES REFERRED TO
- QToggleSwitch was modified from Switch, by Stefan Scherfke [https://stackoverflow.com/a/51825815].


MODIFICATION HISTORY
[ 7/14/2022] Renamed QToggleSwitchPlusLabelsLayout's QToggleSwitch instance to .control, to match QtKit.Layouts.
[ 3/16/2022] Added tiny bundle of laziness QToggleSwitchPlusLabelsLayout.
[ 6/24/2021] Swapped from PyQt5 to the more flexibly-licensed and officially-supported PySide2 (Qt5).
			  As of this time, matplotlib does not support Qt6.
[ 9/ 2/2019] Added QToggleSwitch, a cute lil' toggle switch.

-------------------------------------------------------------------
"""

from PySide6 import QtCore, QtGui, QtWidgets
import logging
logging.basicConfig(level=logging.ERROR)



class QToggleSwitch(QtWidgets.QAbstractButton):
	# Modified from Switch by Stefan Scherfke [https://stackoverflow.com/a/51825815]

	def __init__(self, parent=None, truelabel='✔', falselabel='✕'):
		super().__init__(parent=parent)
		self.setCheckable(True)
		self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

		self._track_radius = 10
		self._thumb_radius = 8

		if len(truelabel) < 2 and len(falselabel) < 2:
			self._track_text_width = 0
			self._left_text_offset = {
				True: 0,
				False: 0,
			},
		else:
			self._track_text_width = max(len(truelabel), len(falselabel))*self._thumb_radius
			self._left_text_offset = {
				True: 2*self._thumb_radius,
				False: max(self._thumb_radius, self._track_radius) - 2*self._thumb_radius,
			}

		self._margin = max(0, self._thumb_radius - self._track_radius)
		self._base_offset = max(self._thumb_radius, self._track_radius)
		self._end_offset = {
			True: lambda: self.width() - self._base_offset,
			False: lambda: self._base_offset,
		}
		self._track_offset = {
			True: lambda: self.width() - self._base_offset,
			False: lambda: self._base_offset,
		}
		self._offset = self._base_offset

		palette = self.palette()
		if self._thumb_radius > self._track_radius:
			self._track_color = {
				True: palette.highlight(),
				False: palette.dark(),
			}
			self._thumb_color = {
				True: palette.highlight(),
				False: palette.light(),
			}
			self._text_color = {
				True: palette.highlightedText().color(),
				False: palette.dark().color(),
			}
			self._thumb_text = {
				True: '',
				False: '',
			}
			self._track_opacity = 0.5
		else:
			self._thumb_color = {
				True: palette.highlightedText(),
				False: palette.light(),
			}
			self._thumb_text = {
				True: truelabel,
				False: falselabel,
			}
			self._track_color = {
				True: palette.highlight(),
				False: palette.dark(),
			}
			if len(self._thumb_text[True]) < 2 and len(self._thumb_text[False]) < 2:
				self._text_color = {
					True: palette.highlight().color(),
					False: palette.dark().color(),
				}
			else:
				self._text_color = {
					True: palette.dark().color(),
					False: palette.highlight().color(),
				}
			self._track_opacity = 1

	@QtCore.Property(int)
	def offset(self):
		return self._offset

	@offset.setter
	def offset(self, value):
		self._offset = value
		self.update()

	def sizeHint(self):  # pylint: disable=invalid-name
		return QtCore.QSize(
			4*self._track_radius + 2*self._margin + self._track_text_width,
			2*self._track_radius + 2*self._margin,
		)

	def setChecked(self, checked):
		super().setChecked(checked)
		self.offset = self._end_offset[checked]()

	def resizeEvent(self, event):
		super().resizeEvent(event)
		self.offset = self._end_offset[self.isChecked()]()

	def paintEvent(self, event):  # pylint: disable=invalid-name, unused-argument
		p = QtGui.QPainter(self)
		p.setRenderHint(QtGui.QPainter.Antialiasing, True)
		p.setPen(QtCore.Qt.NoPen)
		track_opacity = self._track_opacity
		thumb_opacity = 1.0
		text_opacity = 1.0
		if self.isEnabled():
			track_brush = self._track_color[self.isChecked()]
			thumb_brush = self._thumb_color[self.isChecked()]
			text_color = self._text_color[self.isChecked()]
		else:
			track_opacity *= 0.8
			track_brush = self.palette().shadow()
			thumb_brush = self.palette().mid()
			text_color = self.palette().shadow().color()

		# Draw the track
		p.setBrush(track_brush)
		p.setOpacity(track_opacity)
		p.drawRoundedRect(
			self._margin, # x
			self._margin, # y
			self.width() - 2*self._margin, # w
			self.height() - 2*self._margin, # h
			self._track_radius, # xRadius
			self._track_radius, # yRadius
		)
		# Draw the thumb button in its initial-state position
		p.setBrush(thumb_brush)
		p.setOpacity(thumb_opacity)
		p.drawEllipse(
			self.offset - self._thumb_radius, # left
			self._base_offset - self._thumb_radius, # top
			2*self._thumb_radius, # width
			2*self._thumb_radius, # height
		)
		p.setPen(text_color)
		p.setOpacity(text_opacity)
		font = p.font()
		font.setPixelSize(1.3 * self._thumb_radius)
		p.setFont(font)
		texttop = self._base_offset - self._thumb_radius
		textheight = 2*self._thumb_radius
		if len(self._thumb_text[True]) < 2 and len(self._thumb_text[False]) < 2:
			# Text goes on top of the thumb
			textleft = self.offset - self._thumb_radius
			textwidth = 2*self._thumb_radius
		else:
			# Text goes into the track, avoiding the thumb
			# textleft = self.offset - 2*self._thumb_radius
			textleft = self._track_text_width - 0.5*self.offset
			textwidth = self._track_text_width
		p.drawText(QtCore.QRectF(textleft, texttop, textwidth, textheight), QtCore.Qt.AlignCenter, self._thumb_text[self.isChecked()])

	def mouseReleaseEvent(self, event):
		super().mouseReleaseEvent(event)
		# logging.debug("_track_text_width: {!s}, offset: {!s}, text left offset: {!s}".format(self._track_text_width, self.offset, self._track_text_width - 0.5*self.offset)) # diagnostics
		if event.button() == QtCore.Qt.LeftButton:
			anim = QtCore.QPropertyAnimation(self, b'offset', self)
			anim.setDuration(120 + self._track_text_width)
			anim.setStartValue(self.offset)
			anim.setEndValue(self._end_offset[self.isChecked()]())
			anim.start()

	def enterEvent(self, event):
		self.setCursor(QtCore.Qt.PointingHandCursor)
		super().enterEvent(event)







class QToggleSwitchPlusLabelsLayout(QtWidgets.QHBoxLayout):
	# A mini helper that bundles a label and a QToggleSwitch in sheer OO laziness
	
	def __init__(self, rightlabel='', leftlabel='', defaultchecked=False, *args, **kwargs):
		"""
		Prepacks the QHBoxLayout with two labels and a QToggleSwitch... and that's pretty much it.
		"""
		super(QToggleSwitchPlusLabelsLayout, self).__init__(*args, **kwargs)
		self.leftlabel = QtWidgets.QLabel(leftlabel)
		if leftlabel !='':
			self.addWidget(self.leftlabel, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		self.control = QToggleSwitch()
		self.control.setChecked(defaultchecked) # Helps the user locate the mask if switched on before adjusting
		self.addWidget(self.control, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		self.rightlabel = QtWidgets.QLabel(rightlabel)
		if rightlabel !='':
			self.addWidget(self.rightlabel, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
		
		# Adjust spacings
		for childnumber in range(self.count()):
			self.setStretch(childnumber, 1)
			
