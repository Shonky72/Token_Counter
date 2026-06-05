import base64
import hashlib

from token_counter.oauth import (
    OAuthClient,
    build_authorization_url,
    generate_pkce,
    parse_redirect,
)


def test_pkce_challenge_matches_verifier():
    verifier, challenge = generate_pkce()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert challenge == expected
    assert "=" not in challenge  # url-safe, unpadded


def test_pkce_is_random():
    assert generate_pkce()[0] != generate_pkce()[0]


def test_build_authorization_url_contains_required_params():
    client = OAuthClient(
        name="g",
        authorization_endpoint="https://auth.example/authorize",
        token_endpoint="https://auth.example/token",
        client_id="abc.apps",
        scopes=["scope.a", "scope.b"],
    )
    url = build_authorization_url(client, "CHALLENGE", "STATE", "http://127.0.0.1:8799/callback")
    assert url.startswith("https://auth.example/authorize?")
    assert "client_id=abc.apps" in url
    assert "code_challenge=CHALLENGE" in url
    assert "code_challenge_method=S256" in url
    assert "state=STATE" in url
    assert "scope=scope.a+scope.b" in url
    assert "response_type=code" in url


def test_parse_redirect_extracts_code_and_state():
    got = parse_redirect("/callback?code=AUTH_CODE&state=xyz&scope=a")
    assert got["code"] == "AUTH_CODE"
    assert got["state"] == "xyz"


def test_parse_redirect_error():
    got = parse_redirect("/callback?error=access_denied")
    assert got["error"] == "access_denied"
    assert "code" not in got
