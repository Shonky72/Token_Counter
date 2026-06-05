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

echo Step 1/2: installing dependencies ^(this can take a minute^)...
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
echo Step 2/3: generating the app icon...
python -m token_counter icon icon.ico

echo.
echo Step 3/3: building the executable...
python -m PyInstaller --noconsole --onefile --name TokenCounter --paths src ^
  --icon icon.ico --collect-all pystray --collect-all PIL --collect-all keyring ^
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
echo Copy TokenCounter.exe anywhere and double-click to run it.
echo Friends can run the same file and enter their own API keys.
echo.
pause
