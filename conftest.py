# conftest.py
import sys
import os

# Set TCL/TK library environment variables for Windows Python
tcl_path = os.path.join(sys.prefix, "tcl", "tcl8.6")
tk_path = os.path.join(sys.prefix, "tcl", "tk8.6")
if os.path.exists(tcl_path):
    os.environ["TCL_LIBRARY"] = tcl_path
if os.path.exists(tk_path):
    os.environ["TK_LIBRARY"] = tk_path

# Add repo root to sys.path so tests can import flydigi_bs2_controller directly
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
