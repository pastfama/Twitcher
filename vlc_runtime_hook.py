"""PyInstaller runtime hook.

Ensures the python-vlc wrapper finds the bundled libvlc.dll/libvlccore.dll
and plugins directory inside the PyInstaller _MEIPASS extraction directory.
"""
import os
import sys


def _find_bundle_dir():
    """Return the directory where bundled files are extracted."""
    # PyInstaller onefile mode: _MEIPASS points to the extraction dir.
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    # One-dir mode: the exe's directory.
    return os.path.dirname(sys.executable)


_bundle_dir = _find_bundle_dir()

# python-vlc looks for libvlc.dll in PYTHON_VLC_MODULE_PATH then PYTHON_VLC_LIB_PATH.
if os.path.exists(os.path.join(_bundle_dir, "libvlc.dll")):
    os.environ.setdefault("PYTHON_VLC_MODULE_PATH", _bundle_dir)
    os.environ.setdefault("PYTHON_VLC_LIB_PATH", _bundle_dir)

    # VLC resolves plugins relative to libvlccore.dll; setting the
    # module path makes the plugin loader look in <dir>/plugins.
    os.environ.setdefault("PYTHON_VLC_PLUGIN_PATH", os.path.join(_bundle_dir, "plugins"))