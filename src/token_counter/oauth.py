"""OAuth 2.0 Authorization Code + PKCE with a localhost loopback redirect.

Used by the login screen's "Sign in" button for providers that support OAuth
(Google does). You supply an OAuth client (``client_id`` and, for confidential
clients, ``client_secret``) — for Google that's an OAuth client you create in
the Google Cloud console with redirect URI ``http://127.0.0.1:<port>/callback``.

The pure pieces (PKCE generation, auth-URL building, redirect parsing) are
network-free and unit-tested; ``run_loopback_flow`` performs the browser +
token-exchange round trip.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer


@dataclass
class OAuthClient:
    name: str
    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    client_secret: str | None = None
    scopes: list[str] = field(default_factory=list)
    redirect_port: int = 8799


# Common preset. Create the client at https://console.cloud.google.com/apis/credentials
GOOGLE_PRESET = {
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "scopes": ["https://www.googleapis.com/auth/generative-language.retriever"],
}


def generate_pkce() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for the S256 method."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorization_url(
    client: OAuthClient, code_challenge: str, state: str, redirect_uri: str
) -> str:
    params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(client.scopes),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{client.authorization_endpoint}?{urllib.parse.urlencode(params)}"


def parse_redirect(path: str) -> dict:
    """Extract query params (code/state/error) from a redirect request path."""
    query = urllib.parse.urlparse(path).query
    flat = urllib.parse.parse_qs(query)
    return {k: v[0] for k, v in flat.items()}


def exchange_code(
    client: OAuthClient, code: str, code_verifier: str, redirect_uri: str
) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client.client_id,
        "code_verifier": code_verifier,
    }
    if client.client_secret:
        data["client_secret"] = client.client_secret
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        client.token_endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


class _CallbackHandler(BaseHTTPRequestHandler):
    captured: dict = {}

    def log_message(self, *args):  # noqa: D401 - silence
        return

    def do_GET(self):
        type(self).captured = parse_redirect(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        ok = "code" in type(self).captured
        msg = "Sign-in complete — you can close this tab." if ok else "Sign-in failed."
        self.wfile.write(f"<html><body><h3>{msg}</h3></body></html>".encode())


def run_loopback_flow(client: OAuthClient, timeout: float = 180) -> dict:
    """Open the browser, capture the redirect, and exchange for tokens.

    Returns the token bundle (access_token, refresh_token, expires_in, ...).
    Raises ``RuntimeError`` on user cancel/timeout or provider error.
    """
    redirect_uri = f"http://127.0.0.1:{client.redirect_port}/callback"
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(16)

    handler = type("Handler", (_CallbackHandler,), {"captured": {}})
    httpd = HTTPServer(("127.0.0.1", client.redirect_port), handler)
    done = threading.Event()

    def serve():
        while not done.is_set() and not handler.captured:
            httpd.handle_request()
        done.set()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    url = build_authorization_url(client, challenge, state, redirect_uri)
    webbrowser.open(url)

    done.wait(timeout)
    httpd.server_close()
    captured = handler.captured

    if not captured:
        raise RuntimeError("OAuth timed out waiting for the browser redirect")
    if captured.get("error"):
        raise RuntimeError(f"OAuth error: {captured['error']}")
    if captured.get("state") != state:
        raise RuntimeError("OAuth state mismatch (possible CSRF) — aborting")
    code = captured.get("code")
    if not code:
        raise RuntimeError("OAuth redirect did not contain an authorization code")

    return exchange_code(client, code, verifier, redirect_uri)
