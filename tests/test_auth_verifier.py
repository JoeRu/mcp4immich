"""Tests for mcp4immich/auth.py: JWKS cache and token verification."""
import time

import anyio
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp4immich.auth import AuthConfig, JwksCache, JwtTokenVerifier, build_verifier
from auth_fixtures import FakeIssuer


def _config(**overrides) -> AuthConfig:
    values = {
        "issuer": "https://id.example",
        "audience": "client-123",
        "resource_url": "https://mcp.example/mcp",
        "allowed_sub": None,
        "algorithms": ("RS256", "ES256", "EdDSA"),
    }
    values.update(overrides)
    return AuthConfig(**values)


@pytest.fixture
def issuer() -> FakeIssuer:
    return FakeIssuer()


@pytest.fixture
def verifier(issuer) -> JwtTokenVerifier:
    return build_verifier(_config(), fetch=issuer.fetch)


def test_valid_token_is_accepted(issuer, verifier):
    token = issuer.mint()
    result = verifier.verify_sync(token)
    assert result is not None
    assert result.subject == "user-1"
    assert result.client_id == "client-123"
    assert result.scopes == ["openid", "profile"]
    assert result.token == token


def test_async_verify_token_matches_sync(issuer, verifier):
    token = issuer.mint()
    result = anyio.run(verifier.verify_token, token)
    assert result is not None and result.subject == "user-1"


def test_client_id_prefers_explicit_claim(issuer, verifier):
    result = verifier.verify_sync(issuer.mint(client_id="the-client"))
    assert result.client_id == "the-client"


def test_audience_list_containing_expected_value_is_accepted(issuer, verifier):
    result = verifier.verify_sync(issuer.mint(aud=["other", "client-123"]))
    assert result is not None


def test_rejects_wrong_issuer(issuer, verifier):
    assert verifier.verify_sync(issuer.mint(iss="https://evil.example")) is None


def test_rejects_token_for_other_audience(issuer, verifier):
    # Review Focus 1: same issuer, same key, another client -> must not open the MCP.
    assert verifier.verify_sync(issuer.mint(aud="some-other-client")) is None


def test_rejects_token_without_audience(issuer, verifier):
    assert verifier.verify_sync(issuer.mint(aud=None)) is None


def test_rejects_expired_token_beyond_leeway(issuer, verifier):
    past = int(time.time()) - 3600
    assert verifier.verify_sync(issuer.mint(iat=past - 300, nbf=past - 300, exp=past)) is None


def test_accepts_token_expired_within_leeway(issuer, verifier):
    now = int(time.time())
    assert verifier.verify_sync(issuer.mint(exp=now - 30)) is not None


def test_rejects_not_yet_valid_token(issuer, verifier):
    future = int(time.time()) + 3600
    assert verifier.verify_sync(issuer.mint(nbf=future)) is None


def test_rejects_bad_signature(issuer, verifier):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(issuer.claims(), other_key, algorithm="RS256", headers={"kid": issuer.kid})
    assert verifier.verify_sync(forged) is None


def test_rejects_alg_none(issuer, verifier):
    assert verifier.verify_sync(issuer.mint_unsigned()) is None


def test_rejects_hs256_token(issuer, verifier):
    forged = jwt.encode(issuer.claims(), "x" * 32, algorithm="HS256", headers={"kid": issuer.kid})
    assert verifier.verify_sync(forged) is None


def test_rejects_token_without_kid(issuer, verifier):
    token = jwt.encode(issuer.claims(), issuer.private_key, algorithm="RS256")
    assert verifier.verify_sync(token) is None


def test_rejects_garbage(verifier):
    assert verifier.verify_sync("not-a-jwt") is None
    assert verifier.verify_sync("") is None


def test_rejects_missing_sub(issuer, verifier):
    assert verifier.verify_sync(issuer.mint(sub=None)) is None


def test_allowed_sub_enforced(issuer):
    verifier = build_verifier(_config(allowed_sub="user-1"), fetch=issuer.fetch)
    assert verifier.verify_sync(issuer.mint(sub="user-1")) is not None
    assert verifier.verify_sync(issuer.mint(sub="user-2")) is None


def test_key_rotation_is_picked_up_via_refetch(issuer):
    clock = [1000.0]
    jwks = JwksCache(issuer.jwks_uri, issuer.fetch, clock=lambda: clock[0])
    jwks.refresh()
    verifier = JwtTokenVerifier(_config(), jwks)
    issuer.rotate("k2")
    clock[0] += 61
    assert verifier.verify_sync(issuer.mint()) is not None


def test_unknown_kid_refetches_at_most_once_per_interval(issuer):
    # Review Focus 2: random kids must not trigger a JWKS fetch each.
    clock = [1000.0]
    jwks = JwksCache(issuer.jwks_uri, issuer.fetch, clock=lambda: clock[0])
    jwks.refresh()
    assert issuer.fetch_count == 1
    verifier = JwtTokenVerifier(_config(), jwks)
    clock[0] += 61
    for n in range(20):
        assert verifier.verify_sync(issuer.mint_with_headers({"kid": f"random-{n}"})) is None
    assert issuer.fetch_count == 2


def test_jwks_fetch_error_during_verification_rejects(issuer):
    clock = [1000.0]
    calls = {"n": 0}

    def flaky(url):
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("network down")
        return issuer.fetch(url)

    jwks = JwksCache(issuer.jwks_uri, flaky, clock=lambda: clock[0])
    jwks.refresh()
    verifier = JwtTokenVerifier(_config(), jwks)
    clock[0] += 61
    assert verifier.verify_sync(issuer.mint_with_headers({"kid": "unknown"})) is None


def test_build_verifier_fails_closed_when_jwks_unreachable():
    def down(url):
        raise OSError("connection refused")

    with pytest.raises(RuntimeError, match="discovery"):
        build_verifier(_config(), fetch=down)


def test_build_verifier_rejects_issuer_mismatch_in_discovery(issuer):
    def lying(url):
        if url.endswith("openid-configuration"):
            return {"issuer": "https://other.example", "jwks_uri": issuer.jwks_uri}
        return issuer.fetch(url)

    with pytest.raises(RuntimeError, match="issuer"):
        build_verifier(_config(), fetch=lying)


def test_build_verifier_rejects_empty_jwks(issuer):
    def empty(url):
        if url == issuer.jwks_uri:
            return {"keys": []}
        return issuer.fetch(url)

    with pytest.raises(RuntimeError, match="JWKS"):
        build_verifier(_config(), fetch=empty)
