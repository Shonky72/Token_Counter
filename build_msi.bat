@echo off
REM ===================================================================
REM  Token Counter - build a Windows .msi installer
REM  Double-click this. It produces dist\TokenCounter-<version>-win64.msi,
REM  which you (or a friend) can run to install the app like normal software.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo ============================================
echo   Building the Token Counter .msi installer
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found.
  echo Install it from https://www.python.org/downloads/ and tick
  echo "Add python.exe to PATH" on the first screen, then run this again.
  pause
  exit /b 1
)

echo Step 1/3: installing dependencies ^(this can take a minute^)...
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install cx_Freeze
if errorlevel 1 (
  echo [ERROR] Could not install the dependencies. See the messages above.
  pause
  exit /b 1
)

echo.
echo Stamping version + git commit...
python tools\stamp_build.py

echo.
echo Step 2/3: generating the app icon...
python -m token_counter icon icon.ico

echo.
echo Step 3/3: building the installer...
python setup_msi.py bdist_msi
if errorlevel 1 (
  echo [ERROR] The build failed. See the messages above.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   Done!  Your installer is in the "dist" folder:
echo.
dir /b dist\*.msi
echo.
echo ============================================
echo Double-click that .msi to install Token Counter. Share it with friends -
echo each person enters their own API keys after installing.
echo.
pause
