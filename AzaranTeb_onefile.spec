# -*- mode: python ; coding: utf-8 -*-
# One-file build for Windows 7 SP1+ (build with the 32-bit venv for 32-bit):
#   venv38-32\Scripts\python.exe -m PyInstaller --clean -y AzaranTeb_onefile.spec
# PyInstaller 5.13.2 (last line that still targets Python 3.8 on Windows 7).
import glob
import os

# App-local Universal CRT, so the exe also starts on Windows 7 machines that
# never received KB2999226. Taken from the Windows 10/11 SDK redist folder
# matching the build interpreter's bitness; skipped if the SDK is absent.
_ARCH = "x86" if (8 * __import__("struct").calcsize("P")) == 32 else "x64"
_ucrt = []
for _d in sorted(glob.glob(r"C:\Program Files (x86)\Windows Kits\10\Redist\*\ucrt\DLLs\%s" % _ARCH)):
    _ucrt = [(f, ".") for f in glob.glob(os.path.join(_d, "*.dll"))]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=_ucrt,
    datas=[('webapp/static/fonts/Vazirmatn-var.woff2', 'webapp/static/fonts'),
           ('app/resources', 'app/resources')],
    hiddenimports=['PyQt5.QtSvg', 'PyQt5.QtPrintSupport'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The browser UI is not part of the desktop exe.
    excludes=['tkinter', 'webapp', 'fastapi', 'uvicorn', 'starlette',
              'jinja2', 'pydoc', 'unittest'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AzaranTeb',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX-packed Qt DLLs are a common source of crashes
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
