"""Entry point for building a standalone executable with PyInstaller.

    pyinstaller --noconsole --onefile --name TokenCounter --paths src \
        --collect-all pystray --collect-all PIL --collect-all keyring \
        run_token_counter.py

Running ``TokenCounter.exe`` with no arguments starts the tray (the ``run``
command); ``TokenCounter.exe window`` / ``login`` / ``popup`` open those windows.
"""

from token_counter.app import main

if __name__ == "__main__":
    raise SystemExit(main())
