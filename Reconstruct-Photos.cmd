@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
    echo Kullanim: Reconstruct-Photos.cmd "C:\scan-data\ilk-nesne" "C:\COLMAP\COLMAP.bat"
    echo Girdi klasorunde images alt klasoru bulunmali.
    pause
    exit /b 2
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (set "PY=py -3") else (set "PY=python")
if "%~2"=="" (
    %PY% tools\monoscan.py reconstruct "%~1" --mode sparse
) else (
    %PY% tools\monoscan.py reconstruct "%~1" --colmap "%~2" --mode sparse
)
set "EXITCODE=%ERRORLEVEL%"
pause
exit /b %EXITCODE%
