# Scintomatic
#### Merlin L. Mah and Mark L. Felice

![Scintomatic at work. (Spectrum data is a test pattern.)](Scintomatic&#32;at&#32;work.png)

Scintomatic is a simple Python application to receive, display, and record the output of the Hidex Triathler 425-034 or PerkinElmer BetaScout liquid scintillation counters. When one of these instruments is set to the "Commfil v.2" communications protocol, it will output via RS-232 connection a count rate vs. time once per second while collecting data, and a spectrum after finishing; Scintomatic plots this information as it is received, and optionally saves it to a tab-separated text file. 

## Dependencies
* [Python3](https://www.python.org)
* [PySide6](https://wiki.qt.io/Qt_for_Python)
* [pyqtgraph](https://www.pyqtgraph.org)

## Operation
Probably the simplest way is to open a terminal and invoke Python:
```
cd /path/to/scintomatic
python3 Scintomatic.py
```

The Scintomatic window is vertically split into two parts: one collapsible pane each for time and spectrum plots, and a fixed strip at the bottom for serial port selection and messages. Connect your Triathler or BetaScout to your PC or Mac (you'll probably need a null modem cable or adapter, or wire your own with pins 2 and 3 swapped), put the instrument in Commfil v.2 mode, click the serial toggle at Scintomatic's bottom left to activate the connection, and try measuring a sample; the relevant Scintomatic pane should automatically pop up and begin plotting. 

The data in each pane is automatically discarded when new incoming data of the same type is detected, so if you forget to click "Save data..." before starting a new run, you'll lose your precious data. The "Autosave" toggle in each pane ensures this doesn't happen by saving each pane-ful to a timestamped file in the ```scintomatic/Autosave``` directory before it is cleared; however, these aren't auto-deleted if you also manually save the data elsewhere, so you may have to nuke this directory from time to time. To choose a different autosave destination, click on the "Autosave" label next to the toggle.

## Known issues and other notes
As of 2023, we haven't figured out how the transmitted bitsum is computed for the spectrum data. (Trying some common CRC combos is celebrating its first anniversary on our TODO lists.) We also have not tested anywhere near exhaustively for the Triathler/BetaScout's operating modes and options, so it's very possible there is functionality that Scintomatic would not understand. 

Finally, it should be noted that Scintomatic only reads what the Triathler/BetaScout transmits over serial. We believe we did suss out what commands correlate to the instrument's physical buttons, but automating operation was outside the scope we wanted. On the plus side, this probably limits the amount of confusion that Scintomatic can cause. 

## About the authors
Scintomatic was a collaboration between two postdoctoral researchers at the University of Minnesota. Unfortunately, neither of us still works with the scintillation counter we wrote this for, so we probably won't be of much help if you encounter issues. Nevertheless, you're welcome to drop us a line for questions or to say hi (particularly if you're a fellow researcher!)

It should be noted that we wrote Scintomatic with--because of, really--a total lack of access to the manufacturer's optional Commfil software. Without this standard or any documentation to work from, Scintomatic represents a "best guess" at the intended functionality. We haven't done anything remotely resembling exhaustive testing of its accuracy or reliability, and there are very likely operation modes that it is not designed to cope with--heck, we're pretty sure a few basic features are still buggy. In other words: there's no warranty, caveat emptor!

## Legalese
Scintomatic is licensed under GPL-3.0. No warranty is provided and no liability assumed by the authors for data loss, injury, or damage from its use (although we'd be pretty amazed if you managed that!) Do not taunt Scintomatic.
