# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH)
assets_root = project_root / "assets"

hiddenimports = collect_submodules("psutil")

analysis = Analysis(
    ["app.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        ("portable.marker", "."),
        ("VERSION", "."),
        (str(assets_root), "assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "playwright"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="PortableAccountBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(assets_root / "app_icon.ico"),
    version=str(assets_root / "windows_version_info.txt"),
    manifest=str(assets_root / "windows_app.manifest"),
    uac_admin=False,
    uac_uiaccess=False,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PortableAccountBrowser",
)
