#! /usr/bin/python3
"""
--------------------------------------------------------------------
QtKit.FoldawaySplitter (and children)
  by Merlin Mah

Base class for a set of collapsible panels that's essentially an evenly-divided QSplitter.


KNOWN ISSUES AND TODOS



DESIGN NOTES



SOURCES, REFERENCES, AND EXAMPLES REFERRED TO
- Follows [https://stackoverflow.com/a/56806227] and [https://stackoverflow.com/a/22000797].


MODIFICATION HISTORY
[ 3/10/2022] Fixed jerky/interrupted FoldawaySplitter animations caused by minimum widget sizes.
[12/31/2021] First version of FoldawaySplitter, a cousin of FoldawayPanel that subclasses QSplitter.
			  It's themable, more stable, better at layout, but what did it cost?

-------------------------------------------------------------------
"""

from PySide6 import QtCore, QtGui, QtWidgets
import logging
logging.basicConfig(level=logging.ERROR)



class FoldawaySplitter(QtWidgets.QSplitter):
	# Base class for a set of collapsible panels that's essentially an evenly-divided QSplitter.
	# Intended to be inherited by directional-specific children FoldawayHPanel and FoldawayVPanel.
	# Follows [https://stackoverflow.com/a/56806227] and [https://stackoverflow.com/a/22000797].

	def __init__(self, parent=None, title=''):
		# Establish a QSplitter
		super(FoldawaySplitter, self).__init__(parent=parent)

		# Add a blank widget to the QSplitter, because otherwise the first of our widget panels will not get a handle
		thehandler = QtWidgets.QWidget()
		QtWidgets.QSplitter.addWidget(self, thehandler)

		# Animate QSplitter's setSizes() [https://stackoverflow.com/a/56806227]
		self.foldAnimation = QtCore.QVariantAnimation(self)
		self.foldAnimation.setDuration(300)
		self.foldAnimation.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
		self.foldAnimation.setDirection(QtCore.QAbstractAnimation.Forward)
		self.foldAnimation.valueChanged.connect(self.onSizesChanged)
		self.setHandleWidth(32) 

		# User preferences
		self.setSizes([0])


	def createHandle(self):
		"""
		Semi-overrides the original QSplitter addWidget() to add our toggle button to any new handles,
		as suggested by [https://stackoverflow.com/a/22000797]
		and [https://doc.qt.io/qtforpython-5/PySide2/QtWidgets/QSplitterHandle.html].
		"""
		newhandle = QtWidgets.QSplitter.createHandle(self)
		newhandle.handlePlusLayout = QtWidgets.QHBoxLayout(self)
		newhandle.handlePlusLayout.setContentsMargins(0, 0, 0, 0)
		newhandle.handlePlusButton = QtWidgets.QToolButton()
		newhandle.handlePlusButton.setStyleSheet("QToolButton { border: none; }") # Adding 'background: red;' can help with layout debugging
		newhandle.handlePlusButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
		newhandle.handlePlusButton.setArrowType(QtCore.Qt.RightArrow)
		newhandle.handlePlusButton.setText("SHORT WORDS!")
		newhandle.handlePlusButton.setCheckable(True)
		newhandle.handlePlusButton.setChecked(True)
		newhandle.handlePlusButton.clicked.connect(lambda: self.toggle(self.indexOf(newhandle))) # TODO what happens if we later remove or reorder the splitter's widgets?
		newhandle.handlePlusLayout.addWidget(newhandle.handlePlusButton)
		newhandle.setLayout(newhandle.handlePlusLayout)
		return newhandle


	def insertWidget(self, index, widget):
		"""
		Semi-overrides the original QSplitter insertWidget() to help track user-preferred widget sizes.
		"""
		sizes = [1 if prevsize > 0 else 0 for prevsize in self.sizes()]
		retval = QtWidgets.QSplitter.insertWidget(self, index, widget)
		sizes.insert(index, 1)
		self.setSizes(sizes)
		widget.setMinimumSize(1, 1) # Otherwise we'll have jerky animations
		return retval

	def addWidget(self, widget):
		"""
		Semi-overrides the original QSplitter addWidget() to help track user-preferred widget sizes.
		"""
		sizes = [1 if prevsize > 0 else 0 for prevsize in self.sizes()]
		retval = QtWidgets.QSplitter.addWidget(self, widget)
		self.setSizes(sizes + [1])
		widget.setMinimumSize(1, 1) # Otherwise we'll have jerky animations
		return retval


	def labelPanel(self, panelindex, labeltext):
		"""
		Sets the text on a panel's expand/collapse button.
		"""
		self.handle(panelindex).handlePlusButton.setText(labeltext)


	def addtoPanelLabel(self, panelindex, widgetlist):
		"""
		Adds the given list of QWidgets to the indicated panel's handle.
		"""
		for hopefullyawidget in widgetlist:
			self.handle(panelindex).handlePlusLayout.addWidget(hopefullyawidget)
		

	def toggle(self, panelindex):
		"""
		Triggers the panel of given index to expand, if it is not already,
		or collapse, if it is already expanded. This entails changing the button states,
		and reapportioning the sizes of each panel.
		"""
		self.foldingpanelindex = panelindex
		self.prevsizes = self.sizes()
		totalsize = sum(self.prevsizes) # Will be the (non-Retina) pixel dimension
		self.destsizes = [1 if prevsize > 0 else 0 for prevsize in self.prevsizes]
		toggleButton = self.handle(panelindex).handlePlusButton

		# Clicking the button seems to automatically and immediately toggle isChecked, so we act on the new state
		if not toggleButton.isChecked():
			# Collapse
			toggleButton.setArrowType(self.iconCollapsed)
			self.destsizes[panelindex] = 0
		else:
			# Expand
			toggleButton.setArrowType(self.iconExpanded)
			self.destsizes[panelindex] = 1

		self.destsizes[0] = 1 if sum(self.destsizes[1:])==0 else 0
		self.destsizes = [int(totalsize * destsize/sum(self.destsizes)) for destsize in self.destsizes]
		if self.prevsizes[panelindex]==self.destsizes[panelindex]:
			self.setSizes(self.destsizes) # toggle() is also called to set up newly-added widgets
		else:
			self.foldAnimation.setStartValue(self.prevsizes[panelindex])
			self.foldAnimation.setEndValue(self.destsizes[panelindex])
			self.foldAnimation.start()


	@QtCore.Slot(int)
	def onSizesChanged(self, value):
		"""
		Slot which responds to the QVariantAnimation's valueChanged signals.
		"""
		try:
			progress = (value - self.prevsizes[self.foldingpanelindex])/(self.destsizes[self.foldingpanelindex]-self.prevsizes[self.foldingpanelindex])
		except ZeroDivisionError:
			progress = 0 # A filthy cheat, yes
		nowsizes = self.sizes()
		totalsize = sum(nowsizes)
		newsizes_frac = [self.prevsizes[i] + progress*(self.destsizes[i]-self.prevsizes[i]) for i in range(0, len(nowsizes))] # Scaling to actual size might not be necessary? But feels better
		newsizes = [int(totalsize * newsize_frac/sum(newsizes_frac)) for newsize_frac in newsizes_frac]
		newsizes[self.foldingpanelindex] = value
		self.setSizes(newsizes)


	def expand(self, panelindex):
		"""
		Shortcut to set the state of a given panel without having to track it beforehand.
		"""
		toggleButton = self.handle(panelindex).handlePlusButton
		if not toggleButton.isChecked():
			toggleButton.setChecked(True)
		self.toggle(panelindex)

	def collapse(self, panelindex):
		"""
		Shortcut to set the state of a given panel without having to track it beforehand.
		"""
		toggleButton = self.handle(panelindex).handlePlusButton
		if toggleButton.isChecked():
			toggleButton.setChecked(False)
		self.toggle(panelindex)


class FoldawayHSplitter(FoldawaySplitter):
	# With FoldawayPanel, implements a set of horizontally-collapsible panels based on QSplitter.

	def __init__(self, parent=None, title=''):
		super(FoldawayHSplitter, self).__init__(parent=parent, title=title)

		self.iconCollapsed = QtCore.Qt.LeftArrow
		self.iconExpanded = QtCore.Qt.RightArrow
		self.setOrientation(QtCore.Qt.Horizontal)


class FoldawayVSplitter(FoldawaySplitter):
	# With FoldawayPanel, implements a set of vertically-collapsible panels based on QSplitter.

	def __init__(self, parent=None, title=''):
		super(FoldawayVSplitter, self).__init__(parent=parent, title=title)

		self.iconCollapsed = QtCore.Qt.UpArrow
		self.iconExpanded = QtCore.Qt.DownArrow
		self.setOrientation(QtCore.Qt.Vertical)

