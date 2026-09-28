"""Auth end to end through the Starlette app the SDK builds."""
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from mcp4immich.config import AUTH_ENV_VARS
from auth_fixtures import FakeIssuer

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def issuer():
    return FakeIssuer()


@pytest.fixture
def auth_env(monkeypatch):
    for name in AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MCP_AUTH_ISSUER", "https://id.example")
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "client-123")
    monkeypatch.setenv("MCP_AUTH_RESOURCE_URL", "https://mcp.example/mcp")


def _app(issuer):
    from mcp4immich.mcp_app import create_mcp

    with (
        patch("mcp4immich.auth._http_get_json", side_effect=issuer.fetch),
        patch("mcp4immich.mcp_app._resolve_external_domain", return_value=None),
    ):
        server = create_mcp()
    # host="0.0.0.0" keeps the SDK's localhost DNS-rebinding guard out of the
    # way of TestClient's "testserver" Host header, as in production.
    return server.streamable_http_app(host="0.0.0.0")


def test_missing_token_gets_401_with_resource_metadata(auth_env, issuer):
    with TestClient(_app(issuer)) as client:
        response = client.post("/mcp", json=INIT, headers=HEADERS)
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert 'resource_metadata="https://mcp.example/.well-known/oauth-protected-resource/mcp"' in challenge


def test_invalid_token_gets_401(auth_env, issuer):
    with TestClient(_app(issuer)) as client:
        response = client.post(
            "/mcp", json=INIT, headers={**HEADERS, "Authorization": "Bearer nope"}
        )
    assert response.status_code == 401


def test_wrong_audience_token_gets_401(auth_env, issuer):
    token = issuer.mint(aud="some-other-client")
    with TestClient(_app(issuer)) as client:
        response = client.post(
            "/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 401


def test_valid_token_reaches_mcp(auth_env, issuer):
    token = issuer.mint()
    with TestClient(_app(issuer)) as client:
        response = client.post(
            "/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {token}"}
        )
    assert response.status_code == 200


def test_protected_resource_metadata_names_issuer(auth_env, issuer):
    with TestClient(_app(issuer)) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")
    assert response.status_code == 200
    body = response.json()
    assert body["resource"].rstrip("/") == "https://mcp.example/mcp"
    assert [s.rstrip("/") for s in body["authorization_servers"]] == ["https://id.example"]


def test_healthz_stays_open(auth_env, issuer):
    with patch("mcp4immich.http_client._probe", return_value={"ok": True}):
        with TestClient(_app(issuer)) as client:
            response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unreachable_issuer_fails_startup(auth_env):
    from mcp4immich.mcp_app import create_mcp

    with (
        patch("mcp4immich.auth._http_get_json", side_effect=OSError("refused")),
        patch("mcp4immich.mcp_app._resolve_external_domain", return_value=None),
    ):
        with pytest.raises(RuntimeError):
            create_mcp()


def test_no_auth_env_serves_without_token(monkeypatch):
    # Regression: the WireGuard instance must keep working with no auth.
    for name in AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    from mcp4immich.mcp_app import create_mcp

    with patch("mcp4immich.mcp_app._resolve_external_domain", return_value=None):
        server = create_mcp()
    with TestClient(server.streamable_http_app(host="0.0.0.0")) as client:
        response = client.post("/mcp", json=INIT, headers=HEADERS)
    assert response.status_code == 200


def test_auth_with_stdio_transport_is_refused(auth_env, issuer, monkeypatch):
    from mcp4immich import mcp_app

    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    with (
        patch("mcp4immich.auth._http_get_json", side_effect=issuer.fetch),
        patch("mcp4immich.mcp_app._resolve_external_domain", return_value=None),
        patch("mcp4immich.mcp_app.register_prompts_and_resources"),
        patch("mcp4immich.mcp_app._register_tools"),
    ):
        with pytest.raises(ValueError, match="stdio"):
            mcp_app.run()
