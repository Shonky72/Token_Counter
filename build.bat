@echo off
REM ===================================================================
REM  Token Counter - build a standalone Windows .exe
REM  Just double-click this file. It installs what's needed and builds
REM  dist\TokenCounter.exe, which you can share with friends.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   Building TokenCounter.exe
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found.
  echo.
  echo Install Python from https://www.python.org/downloads/ and make sure you
  echo tick "Add python.exe to PATH" on the first screen, then run this again.
  echo.
  pause
  exit /b 1
)

REM Close any running copy so it can't lock files or confuse the rebuild.
taskkill /IM TokenCounter.exe /F >nul 2>nul

echo Step 1/4: installing dependencies ^(this can take a minute^)...
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pyinstaller
if errorlevel 1 (
  echo.
  echo [ERROR] Could not install the dependencies. See the messages above.
  pause
  exit /b 1
)

echo.
echo Step 2/4: stamping version + git commit...
python tools\stamp_build.py

echo.
echo Step 3/4: generating the app icon...
python -m token_counter icon icon.ico
if not exist "icon.ico" (
  echo [ERROR] icon.ico was not created - the icon step failed. Aborting so you
  echo don't get an exe with the wrong icon. See the messages above.
  pause
  exit /b 1
)

echo.
echo Step 4/4: building the executable ^(clean build^)...
python -m PyInstaller --clean --noconfirm --noconsole --onefile --name TokenCounter --paths src ^
  --icon icon.ico --version-file version_info.txt ^
  --collect-all pystray --collect-all PIL --collect-all keyring ^
  run_token_counter.py
if errorlevel 1 (
  echo.
  echo [ERROR] The build failed. See the messages above.
  pause
  exit /b 1
)

echo.
echo Creating a Desktop shortcut...
"dist\TokenCounter.exe" shortcut

echo.
echo ============================================
echo   Done!  Your file is here:
echo   %CD%\dist\TokenCounter.exe
echo   A "Token Counter" shortcut is on your Desktop.
echo ============================================
echo.
echo This build was stamped as:
python -c "import sys; sys.path.insert(0,'src'); import token_counter; print('  Token Counter ' + token_counter.build_string())"
echo (Confirm it in the tray menu's top line, or in
echo  %USERPROFILE%\.token_counter\token_counter.log after launch.)
echo.
echo Copy TokenCounter.exe anywhere and double-click to run it.
echo Friends can run the same file and enter their own API keys.
echo.

set /p launch=Launch Token Counter now? (Y/N):
if /I "%launch%"=="Y" (
  start "" "dist\TokenCounter.exe"
  echo Started! Look for the bar-chart icon near your clock ^(click the ^^ arrow^).
)
echo.
pause
