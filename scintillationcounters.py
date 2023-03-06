"""
--------------------------------------------------------------------
scintillationcounters.py
  by Merlin Mah
Classes to interface with a variety of scintillation counters,
the variety currently comprising just one type of machine.


MODIFICATION HISTORY
[12-23-2021] First version.


KNOWN ISSUES and TODOs



EXAMPLE USAGE
    import scintillationcounters
    bob = scintillationcounters.BGS80PP(name='bob', limits=(-45, 15)) # Say our stage would collide with something at angles > +15
    bob.openRS232port('/dev/ttyUSB0') # On Linux; something like 'ASRL6' on Windows
    bob.home()
    bob.move_absolute(10)


--------------------------------------------------------------------
"""

import InstrumentComm
import re, string # regexp and string classes for response parsing
import numpy as np
import time


class Triathler(InstrumentComm.RS232):
    """
    This class represents the Hidex Triathler 425-034... or the 425-004...
    or whichever terribly-named product this thing is.

    Use an RS-232 null-modem adapter (which swaps one side's RX and TX pins vs. the usual)
    when connecting.

    While the Triathler says plenty, apparently the only commands it takes
    are the sixteen single-byte codes that correspond to the 12 numeric keypad
    and 4 softkey buttons on the physical device.
    """

    def __init__(self, **kwargs):
        """
        Class initialization
        """
        InstrumentComm.RS232.__init__(self, terminator='\n\r', readterminator='\n\r', baudrate=9600, bytesize=8, parity='N', xonxoff=False, rtscts=False, **kwargs) # Non-editable parameters. See manual p.66
        self.fastTimeout = 500 # [msec]


    # def after_open(self):
    #     self.devcomm.timeout = None # Allow read_until() calls to block until a line terminator actually arrives
    #     self.devcomm.write_timeout = 1


    def __exit__(self):
        try:
            self.devcomm.closeport()
        except AttributeError:
            pass



    # LOW-LEVEL COMMUNICATION
    #----------------------------------------------

    def send(self, instr, param=''):
        """
        Issue a command to the Triathler without checking for a reply.
        """
        return self.write(f"{instr}{param}")
        return True

    def query(self, instr, param=''):
        """
        Issue a single questioning command and return the response.
        """
        return self.ask(f"{self.axis}{instr}{param}?") # TODO For now, we assume unqueued responses

    def valueonly(self, valuestring):
        """
        Extract and return only the value from a string response,
        discarding the stage address and command fields.
        """
        return str(valuestring)[4:]


    def read_until(self, untilchar=b'\r'):
        """
        Read until a certain character or string of characters is found.
        Technically the Triathler's output line terminator is a newline and carriage return '\n\r';
        however, the LCD screen updates (that contain time vs counts information) lack the newline,
        which makes for a lot of headache when attempting to parse them, but setting the read terminator
        would cause different headaches with frequent spare '\n's and corrupted binary blocks.
        Therefore, we will expose PySerial's read_until()
        """
        return self.devcomm.read_until(untilchar)


    # HIGHER-LEVEL COMMUNICATION ROUTINES
    #----------------------------------------------

    def setorget(self, commandStr, paramVal=None):
        """
        Issues a command or a query, depending on the absence or presence of
        the second argument.
        """
        if paramVal==None:
            return self.valueonly(self.query(commandStr))
        else:
            return self.send(commandStr, str(paramVal))


    # KEYPAD AND SOFTKEY ENTRIES
    #----------------------------------------------

    def keypad(self, number):
        """
        Issues the command corresponding to pressing one of the numeric keypad buttons;
        specify which with the number argument, an integer from 0 to 9.
        """
        if 0 < int(number) < 9:
            self.write(str(int(number)).encode('latin-1'))
        else:
            raise

    def enter_key(self):
        """
        Hits the keypad Enter key.
        """
        self.write(b'\x3f')

    def delete_key(self):
        """
        Hits the keypad Delete key.
        """
        self.write(b'\x40')


    def start_key(self):
        """
        Hits the Start softkey.
        """
        self.write(b'\x3b')

    def stop_key(self):
        """
        Hits the Stop softkey.
        """
        self.write(b'\x3c')

    def next_key(self):
        """
        Hits the Next softkey.
        """
        self.write(b'\x3d')

    def set_key(self):
        """
        Hits the Set softkey.
        """
        self.write(b'\x3e')




class BetaScout(Triathler):
    """
    This class communicates with the Perkin Elmer BetaScout, which is apparently
    identical to the Hidex Triathler; unsurprisingly, the class is thus
    completely identical to the Triathler's.
    """



#-------------------------------------------------------------------
# Custom exception for scintillationcounter motion control devices

class ScintillationCounterError(InstrumentComm.Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(ScintillationCounterError, self).__init__('ScintillationCounter', errorMessage, proxyerror)
