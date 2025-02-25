#*********************************************
#        Auto-Generated With py2Nsis
#*********************************************

from setuptools import find_packages
packages = find_packages(exclude=["tests"])

import warnings
#ignore the sets DeprecationWarning
warnings.simplefilter('ignore', DeprecationWarning)
import py2exe
warnings.resetwarnings()

from distutils.core import setup

target = {
    'script' : "samurai-ide.py",
    'version' : "2.1",
    'company_name' : "",
    'copyright' : "GPL",
    'name' : "Samurai-IDE",
    'dest_base' : "Samurai-IDE",
    'icon_resources': [(1, "samurai-ide.ico")]
}

setup(
    data_files = [],

    zipfile = None,

    options = {
        "py2exe": {
            "compressed": 0,
              "optimize": 0,
              "includes": ['sip', 'PyQt4.QtNetwork', 'win32com'],
              "excludes": ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email', 'pywin.debugger', 'pywin.debugger.dbgcon', 'pywin.dialogs', 'tcl', 'Tkconstants', 'Tkinter'],
              "packages": packages,
              "bundle_files": 1,
              "dist_dir": "dist",
              "xref": False,
              "skip_archive": False,
              "ascii": False,
              "custom_boot_script": '',
            }
        },
    console = [],
    windows = [target],
    service = [],
    com_server = [],
    ctypes_com_server = []
)
