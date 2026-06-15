"""Best-effort single-instance guard per window, with cross-process focus.

Each named window (``dashboard`` / ``compact`` / ``login`` / ``settings``) binds a
fixed loopback UDP port. The first process to bind *owns* that window; a second
launch fails to bind, fires a "focus" datagram at the owner, and its caller bows
out. The owner runs a tiny listener thread that calls a focus callback (bring the
existing window to the front) for each datagram it receives.

Everything is best-effort: any socket error degrades to "behave like the only
instance", so a window always opens even if the guard can't run.
"""

from __future__ import annotations

import socket
import threading
from typing import Callable

_HOST = "127.0.0.1"
_PORTS = {"dashboard": 49801, "compact": 49802, "login": 49803, "settings": 49804}
_PING = b"tokn-focus"


class SingleInstance:
    """Guard for one named window. Create one, then call :meth:`acquire`."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.port = _PORTS.get(name)
        self._sock: socket.socket | None = None
        self._focus: Callable[[], None] | None = None
        self._thread: threading.Thread | None = None

    def acquire(self) -> bool:
        """``True`` if we now own the window; ``False`` if another instance is
        already running (in which case it's been pinged to come forward and the
        caller should just exit)."""
        if self.port is None:
            return True
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind((_HOST, self.port))
        except OSError:
            # Someone already holds the port -> tell them to focus, then bow out.
            try:
                sock.sendto(_PING, (_HOST, self.port))
            except OSError:
                pass
            finally:
                sock.close()
            return False
        except Exception:  # pragma: no cover - exotic platforms: don't block the UI
            sock.close()
            return True
        self._sock = sock
        return True

    def set_focus_handler(self, fn: Callable[[], None]) -> None:
        """Register the bring-to-front callback and start listening for pings.

        The callback runs on the listener thread; handlers that touch a non
        thread-safe UI toolkit (e.g. Tk) should marshal back to the UI thread
        themselves (``root.after(0, ...)``).
        """
        self._focus = fn
        if self._sock is not None and self._thread is None:
            self._thread = threading.Thread(target=self._listen, daemon=True)
            self._thread.start()

    def _listen(self) -> None:
        sock = self._sock
        if sock is None:
            return
        while True:
            try:
                sock.recvfrom(64)
            except OSError:
                return
            fn = self._focus
            if fn is not None:
                try:
                    fn()
                except Exception:
                    pass

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
