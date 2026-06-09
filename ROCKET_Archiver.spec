# -*- mode: python ; coding: utf-8 -*-
# Сборка Windows: pyinstaller --clean ROCKET_Archiver.spec

from pathlib import Path

project_dir = Path(SPECPATH)

datas = [
    (str(project_dir / "bin"), "bin"),
    (str(project_dir / "img"), "img"),
]

hiddenimports = [
    "archiver_core",
    "extract_ui",
    "windows_assoc",
    "updater",
    "requests",
]

a = Analysis(
    [str(project_dir / "ROCKET_Archiver.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="ROCKET_Archiver_v1.1.3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / "img" / "Icon.ico"),
    version=str(project_dir / "version_info.txt"),
)
