# ZyvoRCS Sender — PyInstaller Spec
# Usage: pyinstaller ZyvoRCS.spec

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[
        # Include adb.exe — put adb.exe in same folder before building
        # ('adb.exe', '.'),
    ],
    datas=[
        ('templates', 'templates'),
        ('static',    'static'),
        ('data',      'data'),
    ],
    hiddenimports=[
        'flask',
        'openpyxl',
        'pystray',
        'PIL',
        'adb_engine',
        'engineio.async_drivers.threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    a.zipfiles,
    a.datas,
    [],
    name='ZyvoRCS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='zyvo_icon.ico',  # Uncomment if you have an .ico file
)
