# Third-party components

Focus Lock uses third-party components under their respective terms. This file does not select a license for Focus Lock's own source code.

- **Python 3.12**: Python Software Foundation license. Source and notices: https://www.python.org/downloads/source/
- **PySide6 / Qt for Python 6.8.3 and Shiboken6**: upstream metadata lists LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only, with a separate commercial option. Source: https://code.qt.io/cgit/pyside/pyside-setup.git/ (tag v6.8.3).
- **Qt 6.8.3**: the Qt libraries distributed with PySide6 retain their component-specific licenses and notices. Source archives: https://download.qt.io/archive/qt/6.8/6.8.3/submodules/
- **psutil 7.2.2**: BSD-3-Clause. Source: https://github.com/giampaolo/psutil
- **PyInstaller 6.22.3**: GPL with its upstream bootloader exception. Source and exception: https://github.com/pyinstaller/pyinstaller

The Windows ZIP includes license texts and installed dependency metadata in its `licenses/` directory. The application repository contains the Python source and build specifications used for the executable. Qt libraries are loaded dynamically by the packaged runtime. For rebuilding with your chosen dependency versions, see the source build instructions in README.md.

Bundled libraries may contain additional third-party components covered by their own notices. Consult the upstream source archives for the full component information.
