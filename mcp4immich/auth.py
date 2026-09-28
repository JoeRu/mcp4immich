"""Inbound OAuth for the MCP endpoint: verify access tokens from an OIDC issuer.

Opt-in: nothing here runs unless MCP_AUTH_ISSUER is set (config.get_auth_settings).
mcp4immich is a pure resource server. It never issues tokens and never sees a
password; Pocket-ID (or any OIDC provider) does that. Every failure path returns
None, which the SDK's bearer middleware turns into a 401 before any tool runs.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

import anyio
import httpx
import jwt
from mcp.server.auth.provider import AccessToken

logger = logging.getLogger(__name__)

JsonFetcher = Callable[[str], dict[str, Any]]


def _http_get_json(url: str) -> dict[str, Any]:
    response = httpx.get(url, timeout=10.0, headers={"Accept": "application/json"})
    response.raise_for_status()
    return response.json()


@dataclass(frozen=True)
class AuthConfig:
    issuer: str
    audience: str
    resource_url: str
    allowed_sub: str | None
    algorithms: tuple[str, ...]
    leeway_seconds: int = 60


class JwksCache:
    """Signing keys by kid. Refetches on an unknown kid, at most once per interval.

    The interval matters: the kid comes from the (unverified) token header, so
    without it anyone could make the server fetch the JWKS once per request.
    """

    def __init__(
        self,
        jwks_uri: str,
        fetch: JsonFetcher,
        min_refetch_interval: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._jwks_uri = jwks_uri
        self._fetch = fetch
        self._min_refetch_interval = min_refetch_interval
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._last_fetch: float | None = None

    def refresh(self) -> None:
        self._last_fetch = self._clock()
        keyset = jwt.PyJWKSet.from_dict(self._fetch(self._jwks_uri))
        self._keys = {key.key_id: key for key in keyset.keys if key.key_id}
        if not self._keys:
            raise jwt.PyJWKSetError("JWKS contains no keys with a kid")

    def get(self, kid: str) -> jwt.PyJWK | None:
        key = self._keys.get(kid)
        if key is not None:
            return key
        if self._last_fetch is not None and (
            self._clock() - self._last_fetch < self._min_refetch_interval
        ):
            return None
        self.refresh()
        return self._keys.get(kid)


class JwtTokenVerifier:
    """Implements the SDK's TokenVerifier protocol for JWT access tokens."""

    def __init__(self, config: AuthConfig, jwks: JwksCache) -> None:
        self._config = config
        self._jwks = jwks

    async def verify_token(self, token: str) -> AccessToken | None:
        # A JWKS refetch is blocking httpx; keep it off the event loop, same
        # pattern as /healthz's probe.
        return await anyio.to_thread.run_sync(self.verify_sync, token)

    def verify_sync(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            logger.info("Rejected bearer token: malformed")
            return None
        alg = header.get("alg")
        if alg not in self._config.algorithms:
            logger.info(f"Rejected bearer token: algorithm {alg!r} not allowed")
            return None
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            logger.info("Rejected bearer token: no kid")
            return None
        try:
            key = self._jwks.get(kid)
        except Exception as exc:
            logger.warning(f"Rejected bearer token: JWKS refresh failed ({type(exc).__name__})")
            return None
        if key is None:
            logger.info("Rejected bearer token: unknown kid")
            return None
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[alg],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            logger.info(f"Rejected bearer token: {type(exc).__name__}")
            return None
        except Exception as exc:
            # Defense in depth: a header alg/JWK key-type mismatch (e.g. an
            # ES256 header paired with an RSA kid) raises TypeError deep
            # inside PyJWT, not PyJWTError. Every failure path here must
            # return None, never raise, or an attacker gets a 500 instead
            # of a 401.
            logger.warning(f"Rejected bearer token: unexpected error during decode ({type(exc).__name__})")
            return None
        subject = str(claims["sub"])
        if self._config.allowed_sub is not None and subject != self._config.allowed_sub:
            logger.warning("Rejected bearer token: subject not allowed")
            return None
        scope = claims.get("scope")
        aud = claims["aud"]
        client_id = claims.get("client_id") or claims.get("azp") or (
            aud if isinstance(aud, str) else self._config.audience
        )
        return AccessToken(
            token=token,
            client_id=str(client_id),
            scopes=scope.split() if isinstance(scope, str) else [],
            expires_at=int(claims["exp"]),
            subject=subject,
            claims=claims,
        )


def build_verifier(config: AuthConfig, fetch: JsonFetcher | None = None) -> JwtTokenVerifier:
    """Discover the issuer's JWKS and load it now, so a broken setup fails at startup."""
    fetch = fetch or _http_get_json
    discovery_url = f"{config.issuer}/.well-known/openid-configuration"
    try:
        discovery = fetch(discovery_url)
    except Exception as exc:
        raise RuntimeError(f"OIDC discovery failed at {discovery_url}: {exc}") from exc
    if str(discovery.get("issuer", "")).rstrip("/") != config.issuer:
        raise RuntimeError(
            f"OIDC discovery issuer {discovery.get('issuer')!r} != MCP_AUTH_ISSUER {config.issuer!r}"
        )
    jwks_uri = discovery.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri.startswith("https://"):
        raise RuntimeError(f"OIDC discovery has no usable https jwks_uri: {jwks_uri!r}")
    jwks = JwksCache(jwks_uri, fetch)
    try:
        jwks.refresh()
    except Exception as exc:
        raise RuntimeError(f"JWKS load failed from {jwks_uri}: {exc}") from exc
    logger.info(f"MCP auth enabled: issuer {config.issuer}, audience {config.audience}")
    return JwtTokenVerifier(config, jwks)
