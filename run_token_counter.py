"""Entry point for building a standalone executable with PyInstaller.

    pyinstaller --noconsole --onefile --name tokn --paths src \
        --collect-all pystray --collect-all PIL --collect-all keyring \
        --collect-data token_counter run_token_counter.py

Running ``tokn.exe`` with no arguments starts the tray (the ``run`` command);
``tokn.exe window`` / ``login`` / ``popup`` open those windows.
"""

from token_counter.app import main

if __name__ == "__main__":
    raise SystemExit(main())
