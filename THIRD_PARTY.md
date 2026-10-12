# Third-party components

- PySide6 / Qt: LGPLv3, GPLv3, or commercial terms, according to the included component. https://doc.qt.io/qtforpython-6/licenses.html
- NumPy: BSD-3-Clause. https://numpy.org/doc/stable/license.html
- SciPy: BSD-3-Clause. https://scipy.org/about.html
- PyInstaller: GPL with a bootloader exception. https://pyinstaller.org/en/stable/license.html
- FFmpeg: license depends on the chosen build; this app requires libx264, commonly making that build GPL. https://ffmpeg.org/legal.html
- x264: GPL or commercial licensing. https://www.videolan.org/developers/x264.html

FFmpeg binaries are supplied by the person building the application and are not present in this repository.
Before redistributing a built installer, include the precise build's license notices and corresponding-source access as required by its license. Place the supplied files in `tools/licenses/`; the build script copies these into the output. Preserve Qt/NumPy/SciPy package license files bundled by PyInstaller. Qt remains dynamically linked in the directory bundle.

This file describes dependencies; it does not replace their licenses.
