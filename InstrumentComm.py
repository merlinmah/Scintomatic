"""
--------------------------------------------------------------------
InstrumentComm
  by Merlin Mah
A series of classes to handle common instrument communication protocols,
such as GPIB, USB-TMC, and RS-232, all inheriting and implementing
shared basic communication functions from the "crossroads" class CommBasics.
This provides something like a shared API to quickly and easily grant
communication abilities to any individual instrument class.



VERSION HISTORY
[12-23-2021] Improved kwargs handling/ignoring for RS-232 and CommBasics.
             Unicode formatting for tobytes()/tostring() is now settable at class instantiation.
             Upgraded error classes, because limiting a commit to a single acutally-needed issue is lame.
[11-22-2021] Removed remaining VISA references from USBTMC.
[10-24-2021] Added support for RS-485.
             Moved basic ask() to CommBasics in order to deduplicate RS485 and RS232.
[ 7- 9-2021] Bug fixes to strip(self.lineterminator) calls and RS232's read() and ask().
[11-11-2020] Reduced default fastTimeout value to 200 ms.
[ 6-29-2020] Added tostring() as the inevitable counterpart of tobytes().
             New subclass for pure VISA instruments, to avoid provoking backend problems.
             USBTMC sheds (explicit) use of VISA.
[ 6-26-2020] Updated exception classes for Python 3.
[ 6-22-2020] Introduced tobytes() for safe, explicitly typed, and Python3-only string-to-byte encoding.
[ 6-20-2020] Clarifications to Python3 string encoding, as needed by RS232.
[ 5-20-2020] Added after_open() so inheritors can add instrument startup steps.
[ 1-16-2020] Updates in support of Python 3 and PyVISA changes.
[10- 1-2019] First field use of RS-232 capability, which means lots more bug fixes.
[ 9-18-2019] Added RS-232 serial to help call interchangeability.
             A few more bug fixes.
[ 3-19-2019] It's raining bugs, ohhh it's raining bugs
[ 3-16-2019] Made USBTMC import on-demand to avoid Windows issues.
[ 2- 5-2019] Added support for USBTMC instruments.
             Instrument exception classes now inherit from a single generic one.
[ 9- 4-2018] First version.


NOTES AND KNOWN ISSUES


USAGE

In a class written for a specific instrument, say a lock-in amplifier:

    import InstrumentComm

    class LIA(InstrumentComm.GPIB, InstrumentComm.PrologixGPIB)

        def __init__(self):
            super(LIA, self).__init__() # Saves us from duplicating all the other lines
            self.lineterminator = 'Dolores\r\n' # This would be a strange protocol

That's it! Class LIA would now possess the openGPIBport() and openPrologixGPIB() methods,
so calling scripts can then do

    import LIA
    lia = LIA.LIA()
    lia.openGPIBport(18) # for a LIA set to GPIB address 18
    lia.write('Do you know where you are?')
    lia.read() # Returns, for example, 'I am in a dream.'


--------------------------------------------------------------------
"""

import pyvisa as visa
import string
import sys
import time
import inspect
from functools import singledispatch # [https://docs.python.org/3/library/functools.html#functools.singledispatch]


class CommBasics(object):

    def __init__(self, terminator='\r\n', readterminator='\r\n', byte_formatting='utf-8', **kwargs):
        """
        CommBasics bundles a few methods which should be shared by all derived classes.
        Note that this class is designed solely to be inherited from, and
        will not work on its own; as such, this __init__() method will mostly
        be called via super().

        Optional argument byte_formatting specifies the name of the byte encoding scheme:
        'utf-8', 'latin-1', 'iso-8859-1', 'unicode_escape' (only for Pandas, apparently), etc.
        Beyond that, kwargs are accepted simply to allow inheriting classes to harmlessly pass
        unexplained keyword arguments intended for use downstream.
        """
        # The hard way of getting singledispatchmethod [https://docs.python.org/3/library/functools.html#functools.singledispatchmethod]
        self.byte_formatting = byte_formatting
        self.tobytes = singledispatch(self.tobytes)
        self.tobytes.register(bytes, self._bytes_tobytes)
        self.tobytes.register(bytearray, self._bytearray_tobytes)
        self.tobytes.register(str, self._str_tobytes)

        self.tostring = singledispatch(self.tostring)
        self.tostring.register(bytes, self._bytes_tostring)
        self.tostring.register(bytearray, self._bytearray_tostring)
        self.tostring.register(str, self._str_tostring)

        # Now we, and all inheriting classes, can convert things
        self.lineterminator = self.tobytes(terminator) # Seems the safest and easiest of [https://stackoverflow.com/a/34870210]
        self.readterminator = self.tobytes(readterminator)


    def write(self, command):
        """
        Send a command to the instrument, appending the instrument's preferred message termination characters.
        """
        self.devcomm.write(self.tobytes(command) + self.lineterminator) # Python3 strings default to Unicode, so need to be explicitly encoded
        return


    def read(self):
        """
        Read a response from the instrument and return it sans
        the instrument's preferred message termination characters.
        """
        #response = str(self.devcomm.readline(), "utf-8").strip(self.lineterminator) # [https://stackoverflow.com/a/34870210]
        #response = str(self.devcomm.read_until(self.readterminator), "utf-8") # [https://stackoverflow.com/a/58329177]
        response = self.tostring(self.devcomm.read()) # [https://stackoverflow.com/a/58329177]
        return response


    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        Included here largely as a prototype, because many inheriting classes
        will override it to use their respective underlying commands
        or add their own treatments.
        """
        self.write(command)
        return self.read()


    def after_open(self):
        """
        Gives inheriting classes a chance to trigger any setup steps
        that their instruments might require immediately after opening communications.
        """
        return True # If not overridden, means open___port() methods return what they used to



# CONVERSION BETWEEN STRINGS AND BYTES
# (For background: [https://stackoverflow.com/q/41030128] or [https://blog.feabhas.com/2019/02/python-3-unicode-and-byte-strings/])

    def tobytes(self, data):
        """
        Converts a string to bytes.
        This function structure is essentially the longhand way [https://stackoverflow.com/a/45916896]
        of getting the functionality of singledispatchmethod while preserving Python3 < 3.8 support.
        tobytes() is the generic version for data types which are none of string, bytes, or bytearray
        (so int, double, etc.)

        By the way, apparently the only difference between bytearray and bytes in Python3 is that
        the former is mutable and the latter is not. [https://stackoverflow.com/a/53754724]
        """
        return str(data, self.byte_formatting).encode(self.byte_formatting)

    def _bytes_tobytes(self, data:bytes):
        return data

    def _bytearray_tobytes(self, data:bytearray):
        return data

    def _str_tobytes(self, data:str):
        return data.encode(self.byte_formatting)


    def tostring(self, data):
        """
        Converts bytes to a string.
        This function structure is essentially the longhand way [https://stackoverflow.com/a/45916896]
        of getting the functionality of singledispatchmethod while preserving Python3 < 3.8 support.
        tostring() is the generic version for data types which are not string.
        """
        return str(data)

    def _bytes_tostring(self, data:bytes):
        return data.decode(self.byte_formatting) # [https://stackoverflow.com/q/14472650] says this is identical to str(data, 'utf-8'), but I like bytes.decode()

    def _bytearray_tostring(self, data:bytearray):
        return str(data, self.byte_formatting)

    def _str_tostring(self, data:str):
        return data



class Instrument_Generic_Exception(Exception):
    def __init__(self, instrumentType, errorMessage="I've made a huge mistake", proxyerror=None):
        self.errorSite = inspect.stack()[1].function
        self.instrumentType = instrumentType
        if proxyerror==None or proxyerror==False: # The raising function probably caused the screwup
            self.proxyError = None
        elif proxyerror==True:
            self.proxyError = inspect.stack()[2].function # Raising function, e.g., set()/get(), is just the messenger
        else:
            self.proxyError = str(proxyerror) # ...whatever you say, boss
        self.errorMessage = errorMessage


    def __str__(self):
        return "ERROR [InstrumentComm.{}.{}{}] {}".format(self.instrumentType, repr(self.errorSite), '' if self.proxyError==None else f" (from {repr(self.proxyError)})", repr(self.errorMessage))




# GPIB

class GPIB(CommBasics):

    def __init__(self, knownGPIBaddrs=None, terminator='\r\n', readterminator='\r\n', **kwargs):
        """
        Communicate with an instrument over GPIB via the Keithley KUSB-488 or
        National Instruments PCI-GPIB adapters.
        """
        super(GPIB, self).__init__(terminator=terminator, readterminator=readterminator, **kwargs)
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s
        self.knownGPIBaddrs = []
        if knownGPIBaddrs!=None:
            try:
                len(knownGPIBaddrs) # Solely to trip the exception for non-arrays
                self.knownGPIBaddrs = knownGPIBaddrs
            except TypeError:
                self.knownGPIBaddrs = [knownGPIBaddrs]

    def __del__(self):
        try:
            self.devcomm.closeport()
        except Exception:
            pass


    def openGPIBport(self, commaddr=None, IDcheck=None):
        """
        Open VISA communications via GPIB. Optional argument commaddr should be
        either a single GPIB address, provided as an integer, or a list of several
        integer GPIB addresses. Optional argument IDcheck should be the handle
        of a method which takes no arguments and ascertains the identity of
        the instrument, i.e. by serial number query.
        """
        if commaddr==None:
            tryports = self.knownGPIBaddrs
        else:
            try:
                tryports = commaddr + self.knownGPIBaddrs
            except TypeError: # commaddr must have been a single int, not a list
                tryports = [commaddr] + self.knownGPIBaddrs
        rm = visa.ResourceManager() # For PyVISA 1.5+ [http://pyvisa.readthedocs.org/en/latest/migrating.html]
        instrList = ''.join(rm.list_resources())
        for tryport in tryports:
            if str(tryport) in instrList:
                try:
                    self.devcomm = rm.open_resource('GPIB::' + str(tryport) + '::INSTR', open_timeout=self.stdTimeout) # [http://pyvisa.readthedocs.io/en/stable/api/resourcemanager.html#pyvisa.highlevel.ResourceManager.open_resource]; WARNING: does not include GPIB board identifier block
                    self.devcomm.timeout = self.fastTimeout # [http://pyvisa.readthedocs.io/en/stable/api/resources.html#pyvisa.resources.Resource.timeout]
                    if IDcheck is not None:
                        return IDcheck()
                except (Instrument_GPIB_Error, AttributeError) as e: # TODO: should also watch for rm.open_resource's exception for unplugged board, etc.--what's that called?
                    raise Instrument_GPIB_Error(f"'GPIB::{tryport}' detected, but error on connection attempt", e)
                else:
                    self._GPIBaddr_ = tryport
                    return self.after_open()
        raise Instrument_GPIB_Error("No instrument detected at addresses {}!".format(tryports))


    def closeport(self):
        self.devcomm.close()


    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        Wrapping here because PyVISA changed it to query(), then apparently to query_ascii_values()
        [https://pyvisa.readthedocs.io/en/latest/api/resources.html#pyvisa.resources.USBRaw.query_ascii_values],
        and because PrologixGPIB and RS232 all have differing methods.
        """
        response = self.tostring(self.devcomm.query_ascii_values(command)).strip(self.tostring(self.lineterminator))
        return response


class Instrument_GPIB_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_GPIB_Error, self).__init__('GPIB', errorMessage, proxyerror)



# Prologix GPIB

class PrologixGPIB(CommBasics):

    def __init__(self, knownGPIBaddrs=None, terminator='\r\n', readterminator='\r\n'):
        """
        Communicate with an instrument over the Prologix GPIB-USB adapter.
        """
        super(PrologixGPIB, self).__init__(terminator=terminator, readterminator=readterminator)
        try:
            import prologix_GPIB # Not great practice [https://stackoverflow.com/q/13395116] but Windows machines have issues... as usual
            self.prologix_GPIB = prologix_GPIB
        except ImportError as e:
            raise Instrument_PrologixGPIB_Error("Import error.\n  Is the file 'prologix_GPIB.py' around?", e)
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s
        self.knownGPIBaddrs = []
        if knownGPIBaddrs!=None:
            try:
                len(knownGPIBaddrs) # Solely to trip the exception for non-arrays
                self.knownGPIBaddrs = knownGPIBaddrs
            except TypeError:
                self.knownGPIBaddrs = [knownGPIBaddrs]

    def __del__(self):
        try:
            self.devcomm.closeport()
        except Exception:
            pass


    def openPrologixGPIB(self, prologix_host, commaddr=None):
        """
        Open communications via Prologix GPIB-USB adapter, by starting up an instance of
        class Prologix_USBtoGPIB_Client using the passed-in, pre-started instance
        of Prologix_USBtoGPIB_Host.
        This function has not been tested on non-Linux operating systems.
        # TODO not sure what multiple tries putting self.knownGPIBaddrs into commaddr will do...
        """
        self.devcomm = self.prologix_GPIB.Prologix_USBtoGPIB_Client(commaddr, prologix_host, timeout_ms=self.fastTimeout)
        return self.after_open()


    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        Wrapping here because PyVISA changed it to query(), then apparently to query_ascii_values()
        [https://pyvisa.readthedocs.io/en/latest/api/resources.html#pyvisa.resources.USBRaw.query_ascii_values],
        and because PrologixGPIB and RS232 all have differing methods.
        """
        response = self.tostring(self.devcomm.ask(command)).strip(self.tostring(self.lineterminator))
        return response


    def closeport(self):
        self.devcomm.close()


class Instrument_PrologixGPIB_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_PrologixGPIB_Error, self).__init__('PrologixGPIB', errorMessage, proxyerror)



# Generic VISA

class VISA(CommBasics):

    def __init__(self, terminator='\r\n', readterminator='\r\n'):
        """
        Communicate with a VISA instrument while trying to avoid any explicit manual specification
        of lower-level backend details. We've found that some instruments are VISA compliant but
        have their own backends with gnarly non-standard behaviors or bugs, so this is one way
        to try and tiptoe around these issues.
        """
        super(VISA, self).__init__(terminator=terminator, readterminator=readterminator)
        if not sys.platform=='win32':
            visa.ResourceManager('@py') # To select the pure-Python pyvisa-py backend [https://pyvisa.readthedocs.io/en/latest/introduction/configuring.html]
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s


    def __del__(self):
        try:
            self.devcomm.closeport()
        except Exception:
            pass


    def openVISAport(self, inVISAstring, IDcheck=None):
        """
        Open VISA communications. Argument inVISAstring should be a string that would appear
        in the desired instrument's VISA identifier; it should be specific enough to reliably identify the instrument.
        """
        rm = visa.ResourceManager()
        instrList = rm.list_resources()
        matchingInstrs = [thisInstr for thisInstr in instrList if str(inVISAstring) in thisInstr] # [https://stackoverflow.com/a/4843172]
        if len(matchingInstrs)==0:
            raise Instrument_VISA_Error(f"Specified VISA string '{vendorIDorVISAstring}' not detected as present.\n    Please check string and try again.")
        elif len(matchingInstrs) > 1:
            raise Instrument_VISA_Error(f"Specified VISA string '{vendorIDorVISAstring}' detected in more than one instrument.\n    Please be more specific.")
        else:
            self.devcomm = rm.open_resource(matchingInstrs[0], open_timeout=self.stdTimeout) # [http://pyvisa.readthedocs.io/en/stable/api/resourcemanager.html#pyvisa.highlevel.ResourceManager.open_resource]
            self.devcomm.write_termination = '' # PyVISA has its own layer [https://pyvisa.readthedocs.io/en/latest/introduction/resources.html?highlight=read_termination#termination-characters]
            self.devcomm.read_termination = ''
        # Finally, check the instrument we've opened for
        if IDcheck is not None:
            return IDcheck()
        else:
            return self.after_open()


    def closeport(self):
        self.devcomm.close()


    def write(self, command):
        """
        Send a command to the instrument, appending the instrument's preferred message termination characters.
        Apparently PyVISA still wants strings...
        """
        self.devcomm.write(self.tostring(command) + self.tostring(self.lineterminator)) # Python3 strings default to Unicode, so need to be explicitly encoded
        return

    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        Wrapping here because PyVISA changed it to query(), then apparently to query_ascii_values()
        [https://pyvisa.readthedocs.io/en/latest/api/resources.html#pyvisa.resources.USBRaw.query_ascii_values],
        and finally decided it ought to parse everything to a float by default
        [https://pyvisa.readthedocs.io/en/latest/api/resources.html?highlight=query#pyvisa.resources.USBRaw.query_ascii_values].
        """
        response = self.tostring(self.devcomm.query_ascii_values(command, 's')).strip(self.tostring(self.lineterminator))
        return response


class Instrument_VISA_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_VISA_Error, self).__init__('VISA', errorMessage, proxyerror)




# USB-TMC

class USBTMC(CommBasics):

    def __init__(self, vendorID=None, productID=None, terminator='\r\n', readterminator='\r\n'):
        """
        Communicate with an instrument over USBTMC (USB Test & Measurement Class),
        a protocol which allows GPIB-like communication over USB.
        See [https://knowledge.ni.com/KnowledgeArticleDetails?id=kA00Z0000019NsmSAE&l=en-US]
        or [http://www.tmatlantic.com/encyclopedia/index.php?ELEMENT_ID=13919]
        for more information.

        On Windows systems, you may have difficulties getting Python to register a USB backend
        [https://github.com/pyusb/pyusb/issues/120] and have to jump through some remarkable hoops (surprise!)
        to attempt to stop the "No backend available errors".
        The prescribed solutions--which apparently each have fairly poor success rates--usually involve
        downloading libusb and copying its DLLs into system directories. [https://stackoverflow.com/a/58213525]
        (By the way, "python -m site" shows you where Python and its directories are hiding today.)
        """
        super(USBTMC, self).__init__(terminator=terminator, readterminator=readterminator)
        try:
            # import usb.core as USBcore # To detect 'Errno 2: Entity not found' on Windows
            import usbtmc as PyUSBTMC # Not great practice [https://stackoverflow.com/q/13395116] but Windows machines have issues... as usual
            self.PyUSBTMC = PyUSBTMC
        except ImportError as e:
            raise Instrument_USBTMC_Error("Import error.\n  Have you installed both python-usbtmc and pyusb (python-usb)?", e)
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s

        # Allow descendants to store individual device identifiers at initialization
        self.vendorID = vendorID
        self.productID = productID



    def __del__(self):
        try:
            self.devcomm.closeport()
        except Exception:
            pass


    def openUSBTMCport(self, vendorID=None, productID=None, IDcheck=None):
        """
        Open communications via USBTMC. Argument commaddr should be either
        a single USB identifier, provided as an TODO, or TODO.
        Optional argument IDcheck should be the handle of a method
        which takes no arguments and ascertains the identity of the instrument,
        i.e., by serial number query.
        """
        if productID==None and vendorID==None:
            # Use values stored at initialization
            productID = self.productID
            vendorID = self.vendorID

        devList = self.PyUSBTMC.list_devices()
        if len(devList)==0:
            raise Instrument_USBTMC_Error("No USBTMC instruments seen as connected!")
        if vendorID==None and productID==None:
            # Maybe the lazy user knows there's only one USBTMC instrument connected?
            if not len(devList)==1: # ...nope
                raise Instrument_USBTMC_Error("Please supply a (separated) 'vendorID':'productID' pair!")
        else:
            if productID==None:
                matchingDevs = [thisDev for thisDev in devList if vendorID==thisDev.idVendor] # [https://stackoverflow.com/a/4843172]
            elif vendorID==None:
                matchingDevs = [thisDev for thisDev in devList if productID==thisDev.idProduct]
            else:
                matchingDevs = [thisDev for thisDev in devList if (productID==thisDev.idProduct and vendorID==thisDev.idVendor)]
            if len(matchingDevs) > 1:
                raise Instrument_USBTMC_Error(f" More than one--{len(matchingDevs)}, to be precise--connected USB devices match the given criteria.\n    Please try being more specific?")
            elif len(matchingDevs) < 1:
                raise Instrument_USBTMC_Error(f"No connected USB devices were found to match the given criteria.\n    Check plugs?")
            # Finally, opening time
            try:
                foundvendorID = matchingDevs[0].idVendor
                foundproductID = matchingDevs[0].idProduct
                self.devcomm = self.PyUSBTMC.Instrument(foundvendorID, foundproductID) # Further filtering by serial number [https://github.com/python-ivi/python-usbtmc] is not a concern until the lab has two of any instrument
            except self.PyUSBTMC.usbtmc.UsbtmcException as e:
                print(e) # diagnostics
                print(hex(vendorIDorVISAstring)) # diagnostics
                print(hex(productID)) # diagnostics
                raise Instrument_USBTMC_Error(f"Error opening USB device '{hex(vendorIDorVISAstring)}:{hex(productID)}'\n", e)
        # Check the device we've opened
        if IDcheck is not None:
            return IDcheck()
        else:
            return self.after_open()


    def closeport(self):
        self.devcomm.close()


    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        Python-USBTMC stills calls this ask(), unlike PyVISA's rebranding to query_*().
        """
        response = str(self.devcomm.ask(command)).strip(self.tostring(self.lineterminator))
        return response


class Instrument_USBTMC_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_USBTMC_Error, self).__init__('USBTMC', errorMessage, proxyerror)



# RS-232 serial

class RS232(CommBasics):

    def __init__(self, knownRS232addrs=None, terminator='\r\n', readterminator='\r\n', **kwargs):
        """
        Communicate with an instrument over RS-232 serial.
        Any additional PySerial-relevant keyword=value arguments
        (see the list self.pyserialparams for the keywords)
        will be stored and passed to openRS232port() when it is invoked.
        """
        super(RS232, self).__init__(terminator=terminator, readterminator=readterminator, **kwargs)
        import serial # Only available to this scope, but not necessarily bad [https://stackoverflow.com/q/13395116]
        self.pyserial = serial
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s
        self.knownRS232addrs = [] # TODO kept for call compatibility, but maybe serial shouldn't have these...
        if knownRS232addrs!=None:
            try:
                len(knownRS232addrs) # Solely to trip the exception for non-arrays
                self.knownRS232addrs = knownRS232addrs
            except TypeError:
                self.knownRS232addrs = [knownRS232addrs]
        self.RS232params = {'timeout': self.stdTimeout/1000, 'write_timeout': self.stdTimeout/1000}
        self.pyserialparams = ['port', 'baudrate', 'bytesize', 'parity', 'stopbits', 'xonxoff', 'rtscts', 'dsrdtr', 'inter_byte_timeout', 'exclusive'] # [https://pyserial.readthedocs.io/en/latest/pyserial_api.html]
        self.RS232params.update({kw: arg for kw, arg in kwargs.items() if kw in self.pyserialparams}) # Store any additional parameters recognized as serial parameters
        print("RS232params: {!s}".format(self.RS232params)) # diagnostics
        print("knownRS232addrs: {!s}".format(self.knownRS232addrs)) # diagnostics

    def __del__(self):
        try:
            self.devcomm.close()
        except Exception:
            pass


    def openRS232port(self, commaddr, IDcheck=None, **kwargs):
        """
        Open serial communications via RS-232. Argument commaddr should be
        a single COM port number, /dev/tty* path, or /dev/serial/by-id/* path,
        provided as a string.
        Optional argument IDcheck should be the handle of a method which takes no arguments
        and ascertains the identity of the instrument, i.e. by serial number query.
        Any additional arguments are passed directly to PySerial invocation.
        As a reminder, serial.Serial()'s kwargs can include (but are not limited to):
        baudrate, bytesize, parity, stopbits, xonxoff, rtscts.
        [https://pyserial.readthedocs.io/en/latest/pyserial_api.html]
        """
        if commaddr==None:
            tryports = self.knownRS232addrs
        else:
            tryports = [commaddr] + self.knownRS232addrs
        serialparams = self.RS232params
        serialparams.update({kw: arg for kw, arg in kwargs.items() if kw in self.pyserialparams}) # Store any additional parameters recognized as serial parameters
        for tryport in tryports:
            try:
                self.devcomm = self.pyserial.Serial(tryport, **serialparams)
                if IDcheck is not None:
                    return IDcheck()
            except (self.pyserial.SerialException, AttributeError) as e:
                raise Instrument_RS232_Error(f"Error on connection attempt to serial '{tryport}': ", e)
            else:
                self._RS232addr_ = tryport
                return self.after_open()
        raise Instrument_RS232_Error("No instrument detected at addresses {}!".format(tryports))


    def closeport(self):
        self.devcomm.close()


    def read(self):
        """
        Read a response from the instrument and return it
        sans the instrument's preferred message termination characters.
        PySerial offers read_until(), which is convenient.
        """
        response = self.tostring(self.devcomm.read_until(self.readterminator)).strip(self.tostring(self.lineterminator)) # [https://stackoverflow.com/a/58329177]
        return response



class Instrument_RS232_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_RS232_Error, self).__init__('RS-232', errorMessage, proxyerror)






# RS-485 serial

class RS485(CommBasics):

    def __init__(self, adapter_serial=None, terminator='\r\n', readterminator='\r\n', **kwargs):
        """
        Communicate with an instrument over RS-485.
        Uses pylibftdi as a backend, since PySerial's ostensible RS-485 support doesn't seem to work.
        As usual, any serial communication parameters passed in **kwargs
        are stored for use by openRS485port(), so subclassing instruments
        can declare these ahead of time without having to override the method.
        """
        super(RS485, self).__init__(terminator=terminator, readterminator=readterminator)
        import pylibftdi # Only available to this scope, but not necessarily bad [https://stackoverflow.com/q/13395116]
        self.pylibftdi = pylibftdi
        self.stdTimeout = 2000 # [msec] default timeout length
        self.fastTimeout = 200 # [msec] timeout for routine things such as read()s
        self.pauseTime = 0.01 # [msec] some adapters/devices seem to be a tad slow

        self.serialparams = {'timeout': self.stdTimeout/1000, 'write_timeout': self.stdTimeout/1000}
        self.serialparams.update(kwargs) # Store any additional parameters

    def __del__(self):
        try:
            self.devcomm.close()
        except Exception:
            pass


    def openRS485port(self, adapter_serial=None, IDcheck=None, **kwargs):
        """
        Open communications via RS-485.
        Backend pylibftdi offers much fewer built-in configuration parameters
        (referring most instead to the underlying libftdi calls)
        so we're just ignoring self.serialparams for now.
        """
        libftdi_devs = self.pylibftdi.Driver().list_devices() # List of triples: [vendor, product, serial]
        found_serials = [founddev[2] for founddev in libftdi_devs]
        if len(libftdi_devs)==0:
            raise Instrument_RS485_Error(f"libftdi could not find any RS-485 USB adapters!")
        elif adapter_serial in found_serials:
            try:
                self.devcomm = self.pylibftdi.Device(device_ID=adapter_serial, mode='t')
            except AttributeError as e: # TODO check list of targeted exceptions
                raise Instrument_RS485_Error(f"RS-485 USB adapter with serial '{adapter_serial}' detected, but error on connection attempt: ", e)
        elif adapter_serial!=None:
            raise Instrument_RS485_Error(f"No RS-485 USB adapter found with specified serial '{adapter_serial}'!")
        else: # Okay, just glom onto the first one that works
            for found_serial in found_serials:
                try:
                    self.devcomm = self.pylibftdi.Device(device_ID=found_serial, mode='t')
                    break
                except AttributeError as e: # TODO check list of targeted exceptions
                    pass
            else:
                raise Instrument_RS485_Error(f"Tried {len(found_serials)} found RS-485 USB adapters, but none successfully opened!")
        if 'baudrate' in self.serialparams and self.serialparams['baudrate'] is not None:
            self.devcomm.baudrate = self.serialparams['baudrate']
        if IDcheck is not None:
            return IDcheck()
        return self.after_open()


    def closeport(self):
        self.devcomm.close()


    def read(self):
        """
        Read a response from the instrument and return it
        sans the instrument's preferred message termination characters.
        pylibftdi's read() requires a length in bytes to be specified, but
        the module also offers readline().
        """
        response = self.tostring(self.devcomm.readline()).strip(self.tostring(self.lineterminator)) # [https://stackoverflow.com/a/58329177]
        return response

    def ask(self, command):
        """
        Send a response-expected command to the instrument and return the response.
        This override is necessary because, at least with some devices and adapters,
        there seems to be a slight delay between command issuance and response.
        """
        self.write(command)
        time.sleep(self.pauseTime)
        return self.read()



class Instrument_RS485_Error(Instrument_Generic_Exception):
    def __init__(self, errorMessage='', proxyerror=None):
        super(Instrument_RS485_Error, self).__init__('RS-485', errorMessage, proxyerror)
