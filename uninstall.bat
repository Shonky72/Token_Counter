@echo off
REM ===================================================================
REM  Token Counter - uninstall
REM  Removes: the "launch on startup" entry, the Desktop shortcut, and
REM  your saved API keys. Does NOT delete the program files.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo This will remove:
echo   - the "launch on Windows startup" entry
echo   - the "Token Counter" Desktop shortcut
echo   - your saved API keys (from Windows Credential Manager)
echo.
set /p ok=Continue? (Y/N):
if /I not "%ok%"=="Y" (
  echo Cancelled.
  pause
  exit /b 0
)

echo.
if exist "dist\TokenCounter.exe" (
  "dist\TokenCounter.exe" uninstall
) else (
  python -m token_counter uninstall
)

echo.
echo Done. You can now delete the TokenCounter.exe file if you wish.
pause
