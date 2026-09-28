"""Tests for MCP_AUTH_* parsing in mcp4immich/config.py."""
import pytest

from mcp4immich.config import AUTH_ENV_VARS, get_auth_settings


@pytest.fixture(autouse=True)
def _clean_auth_env(monkeypatch):
    for name in AUTH_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _set_required(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_ISSUER", "https://id.example")
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "client-123")
    monkeypatch.setenv("MCP_AUTH_RESOURCE_URL", "https://mcp.example/mcp")


def test_no_auth_env_means_auth_disabled():
    assert get_auth_settings() is None


def test_full_config_parses_with_default_algorithms(monkeypatch):
    _set_required(monkeypatch)
    settings = get_auth_settings()
    assert settings == {
        "issuer": "https://id.example",
        "audience": "client-123",
        "resource_url": "https://mcp.example/mcp",
        "allowed_sub": None,
        "algorithms": ("RS256", "ES256", "EdDSA"),
    }


def test_issuer_trailing_slash_is_stripped(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("MCP_AUTH_ISSUER", "https://id.example/")
    assert get_auth_settings()["issuer"] == "https://id.example"


def test_allowed_sub_and_algorithms_are_read(monkeypatch):
    _set_required(monkeypatch)
    monkeypatch.setenv("MCP_AUTH_ALLOWED_SUB", "user-1")
    monkeypatch.setenv("MCP_AUTH_ALGORITHMS", "RS256, ES256")
    settings = get_auth_settings()
    assert settings["allowed_sub"] == "user-1"
    assert settings["algorithms"] == ("RS256", "ES256")


@pytest.mark.parametrize(
    "missing", ["MCP_AUTH_ISSUER", "MCP_AUTH_AUDIENCE", "MCP_AUTH_RESOURCE_URL"]
)
def test_partial_config_fails_closed(monkeypatch, missing):
    _set_required(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match=missing):
        get_auth_settings()


def test_only_optional_var_set_still_fails_closed(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_ALLOWED_SUB", "user-1")
    with pytest.raises(ValueError, match="partially configured"):
        get_auth_settings()


@pytest.mark.parametrize("name", ["MCP_AUTH_ISSUER", "MCP_AUTH_RESOURCE_URL"])
def test_http_urls_are_rejected(monkeypatch, name):
    _set_required(monkeypatch)
    monkeypatch.setenv(name, "http://insecure.example")
    with pytest.raises(ValueError, match="https://"):
        get_auth_settings()


@pytest.mark.parametrize("alg", ["none", "HS256", "hs512"])
def test_symmetric_and_none_algorithms_are_refused(monkeypatch, alg):
    _set_required(monkeypatch)
    monkeypatch.setenv("MCP_AUTH_ALGORITHMS", f"RS256,{alg}")
    with pytest.raises(ValueError, match="not allowed"):
        get_auth_settings()
