@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Kullanim: Reconstruct-Photos.cmd "C:\scan-data\ilk-nesne" [focal_px]
  echo Fotograf bazli rekonstruksiyon icin session.json veya focal_px gerekli.
  exit /b 2
)
where py >nul 2>nul
if %ERRORLEVEL%==0 (set "PY=py -3") else (set "PY=python")
if "%~2"=="" (
  %PY% tools\monoscan.py reconstruct "%~1" --mode photo-only
) else (
  %PY% tools\monoscan.py reconstruct "%~1" --mode photo-only --focal-px %~2
)
exit /b %ERRORLEVEL%
