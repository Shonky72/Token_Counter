"""A tiny localhost HTTP server for reporting usage in real time.

Your application code POSTs one record per LLM call; the next 30s refresh picks
it up. Bound to 127.0.0.1 by default — it is a local sidecar, not a public API.

    POST /usage
    {"provider": "claude", "model": "claude-opus-4-8",
     "input_tokens": 1200, "output_tokens": 340,
     "cache_read_tokens": 0, "cache_creation_tokens": 0}

    GET /healthz  -> {"status": "ok"}

Example client (drop in after any Anthropic/Gemini/OpenAI call)::

    import urllib.request, json
    def report(provider, model, usage):
        body = json.dumps({"provider": provider, "model": model,
                           "input_tokens": usage.input_tokens,
                           "output_tokens": usage.output_tokens}).encode()
        urllib.request.urlopen(
            "http://127.0.0.1:8787/usage", data=body, timeout=2)
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import ServerConfig
from .ledger import Ledger

_INT_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
)


def _make_handler(ledger: Ledger):
    class Handler(BaseHTTPRequestHandler):
        # Silence the default noisy logging to stderr.
        def log_message(self, *args):  # noqa: D401
            return

        def _json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip("/") == "/healthz":
                self._json(200, {"status": "ok"})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path.rstrip("/") != "/usage":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(400, {"error": f"invalid JSON: {exc}"})
                return

            provider = data.get("provider")
            model = data.get("model")
            if not provider or not model:
                self._json(400, {"error": "'provider' and 'model' are required"})
                return

            try:
                counts = {f: int(data.get(f, 0) or 0) for f in _INT_FIELDS}
            except (TypeError, ValueError) as exc:
                self._json(400, {"error": f"token fields must be integers: {exc}"})
                return

            ledger.record(provider=str(provider), model=str(model), **counts)
            self._json(202, {"status": "recorded"})

    return Handler


class UsageServer:
    """Runs the HTTP server on a background thread."""

    def __init__(self, config: ServerConfig, ledger: Ledger):
        self.config = config
        self._httpd = ThreadingHTTPServer(
            (config.host, config.port), _make_handler(ledger)
        )
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="usage-server", daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    @property
    def address(self) -> str:
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}"
