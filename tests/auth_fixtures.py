"""A fake OIDC issuer for auth tests: one RSA key, discovery, JWKS, minting."""
from __future__ import annotations

import base64
import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeIssuer:
    def __init__(self, issuer: str = "https://id.example", kid: str = "k1") -> None:
        self.issuer = issuer
        self.jwks_uri = f"{issuer}/.well-known/jwks.json"
        self.fetch_count = 0
        self.rotate(kid)

    def rotate(self, new_kid: str) -> None:
        self.kid = new_kid
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.private_key.public_key()))
        jwk.update({"kid": new_kid, "use": "sig", "alg": "RS256"})
        self.jwks = {"keys": [jwk]}

    @property
    def discovery(self) -> dict[str, Any]:
        return {"issuer": self.issuer, "jwks_uri": self.jwks_uri}

    def fetch(self, url: str) -> dict[str, Any]:
        if url == f"{self.issuer}/.well-known/openid-configuration":
            return self.discovery
        if url == self.jwks_uri:
            self.fetch_count += 1
            return self.jwks
        raise AssertionError(f"unexpected fetch {url}")

    def claims(self, **overrides: Any) -> dict[str, Any]:
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": "client-123",
            "sub": "user-1",
            "iat": now,
            "nbf": now,
            "exp": now + 300,
            "scope": "openid profile",
        }
        claims.update(overrides)
        return {k: v for k, v in claims.items() if v is not None}

    def mint(self, **overrides: Any) -> str:
        return self.mint_with_headers({}, **overrides)

    def mint_with_headers(self, headers: dict[str, Any], **overrides: Any) -> str:
        return jwt.encode(
            self.claims(**overrides),
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid, **headers},
        )

    def mint_unsigned(self, **overrides: Any) -> str:
        """alg=none token, built by hand: PyJWT will not produce one."""
        header = _b64url(json.dumps({"alg": "none", "kid": self.kid}).encode())
        payload = _b64url(json.dumps(self.claims(**overrides)).encode())
        return f"{header}.{payload}."
