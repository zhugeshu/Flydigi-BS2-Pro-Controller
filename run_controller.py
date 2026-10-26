import os
import sys

# Ensure root dir and PyInstaller bundle dir are in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

if getattr(sys, "frozen", False):
    bundle_dir = getattr(sys, "_MEIPASS", root_dir)
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

from flydigi_bs2_controller.main import main

if __name__ == "__main__":
    main()
