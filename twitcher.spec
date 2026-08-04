# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Twitcher.

Builds a Windows executable that bundles:
  - PySide6 (LGPLv3 — dynamic linking, license notice included)
  - requests (Apache 2.0)
  - streamlink (ISC/BSD)
  - Python runtime (PSF)

VLC is NOT bundled (too large, LGPL). The app detects a system VLC install
at runtime and shows a friendly error if not found.

Usage:
    pyinstaller twitcher.spec
    # or:
    powershell -File build_exe.ps1
"""

import os

block_cipher = None

a = Analysis(
    ['twitcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include config files
        ('twitch_api/config.yaml', 'twitch_api'),
        # Include icon
        ('twitcher.ico', '.'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'requests',
        'streamlink',
        # Ensure all twitch_api mixins are bundled
        'twitch_api.auth',
        'twitch_api.channels',
        'twitch_api.chat',
        'twitch_api.clips',
        'twitch_api.eventsub',
        'twitch_api.games',
        'twitch_api.rewards',
        'twitch_api.streams',
        'twitch_api.users',
        # Ensure core modules are bundled
        'core.analytics_engine',
        'core.channel_history',
        'core.dispatcher',
        'core.raid_monitor',
        'core.stream_resolver',
        'core.streamer_history',
        'core.time_boss',
        'core.viewer_monitor',
        'core.viewer_tracker',
        'core.workers',
        # Ensure widgets are bundled
        'widgets.mom.mom_widget',
        'widgets.sullygoose.sullygoose_widget',
        'widgets.viewer_graph',
        'widgets.indicators',
        # SullyGoose API
        'sullygoose_api.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude tests from the build
        'tests',
        'pytest',
        # Exclude unused modules
        'convert_icon',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Twitcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'vcruntime140.dll',
        'python3.dll',
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
    ],
    runtime_tmpdir=None,
    console=False,  # GUI app — no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='twitcher.ico',
)