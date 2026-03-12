#!/usr/bin/env python3
"""Test that renderdoc.pyd can be imported"""
import sys
import os

# Add the pymodules directory to path
pyd_path = r'd:\Code\git\renderdoc\x64\Development\pymodules'
sys.path.insert(0, pyd_path)

# Add DLL directory for dependencies
# For Python 3.6, we need to modify PATH (add_dll_directory is 3.8+)
dll_path = r'd:\Code\git\renderdoc\x64\Development'
os.environ['PATH'] = dll_path + os.pathsep + os.environ.get('PATH', '')

# Also try add_dll_directory if available (Python 3.8+)
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(dll_path)

try:
    import renderdoc as rd
    print("=" * 50)
    print("SUCCESS: renderdoc module imported!")
    print("=" * 50)
    
    # Test some basic attributes
    if hasattr(rd, 'GetVersionString'):
        print("Version: {}".format(rd.GetVersionString()))
    
    # List available classes/functions
    public_attrs = [a for a in dir(rd) if not a.startswith('_')]
    print("\nAvailable API items: {}".format(len(public_attrs)))
    print("Sample items:", public_attrs[:10], "...")
    
except ImportError as e:
    print("FAILED to import: {}".format(e))
    sys.exit(1)
except Exception as e:
    print("ERROR: {}".format(e))
    sys.exit(1)