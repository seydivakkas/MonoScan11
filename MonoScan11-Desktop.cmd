@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 scripts\monoscan_desktop.py
) else (
    python scripts\monoscan_desktop.py
)
if errorlevel 1 (
    echo MonoScan11 masaustu uygulamasi baslatilamadi.
    echo Python 3.11 veya uzeri, Tkinter ve requirements-native.txt gereklidir.
    pause
)
endlocal
