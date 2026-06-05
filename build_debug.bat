@echo off
REM ===================================================================
REM  Token Counter - DEBUG build (keeps a console window open)
REM  Use this if the normal build "runs but nothing shows". The console
REM  version prints errors directly instead of hiding them, so you can
REM  see exactly what's failing on startup.
REM  Output: dist\TokenCounter-debug.exe   (run it from a terminal)
REM ===================================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found. Install from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH", then run this again.
  pause
  exit /b 1
)

taskkill /IM TokenCounter-debug.exe /F >nul 2>nul

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pyinstaller
python tools\stamp_build.py
python -m token_counter icon icon.ico

echo.
echo Building DEBUG executable (with a console window)...
python -m PyInstaller --clean --noconfirm --console --onefile --name TokenCounter-debug --paths src ^
  --icon icon.ico --version-file version_info.txt ^
  --collect-all pystray --collect-all PIL --collect-all keyring ^
  run_token_counter.py
if errorlevel 1 (
  echo [ERROR] Build failed. See the messages above.
  pause
  exit /b 1
)

echo.
echo Done: dist\TokenCounter-debug.exe
echo Run it from a terminal so you can read any startup errors:
echo   dist\TokenCounter-debug.exe
echo.
pause
