import logging
import os
import base64
from typing import Any

import httpx

from .config import _get_config
from .constants import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


_TEXT_CONTENT_TYPE_TOKENS = (
    "text/",
    "application/json",
    "application/problem+json",
    "application/xml",
    "application/xhtml+xml",
    "application/javascript",
)


def _is_textual_content_type(content_type: str) -> bool:
    lowered = (content_type or "").lower()
    if any(token in lowered for token in _TEXT_CONTENT_TYPE_TOKENS):
        return True
    return "charset=" in lowered


class ImmichError(Exception):
    """Base exception for Immich API interactions."""


class ImmichAPIError(ImmichError):
    """Raised when the Immich API returns an error status code."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Immich API error (HTTP {status_code}): {detail}")


class ImmichNetworkError(ImmichError):
    """Raised when a network error occurs while communicating with Immich."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"Network error: {detail}")


class ImmichConfigError(ImmichError):
    """Raised when there is a configuration error."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"Configuration error: {detail}")


def _build_headers(
    config: dict[str, str],
    require_auth: bool,
    extra_headers: dict[str, Any] | None = None,
) -> dict[str, str]:
    headers = {"accept": "application/json"}
    if config["api_key"]:
        headers["x-api-key"] = config["api_key"]
    if config["api_token"]:
        headers["authorization"] = f"Bearer {config['api_token']}"
    if require_auth and not (config["api_key"] or config["api_token"]):
        raise ValueError(
            "IMMICH_API_KEY or IMMICH_API_TOKEN must be set for this call"
        )
    if extra_headers:
        headers.update({str(k): str(v) for k, v in extra_headers.items()})
    return headers


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    require_auth: bool = False,
    extra_headers: dict[str, Any] | None = None,
) -> Any:
    try:
        config = _get_config()
        url = f"{config['base_url']}{path}"
        headers = _build_headers(config, require_auth, extra_headers)
    except ValueError as exc:
        raise ImmichConfigError(str(exc)) from exc

    # Warn if credentials are sent over plain HTTP
    has_credentials = bool(config["api_key"] or config["api_token"])
    if has_credentials and config["base_url"].startswith("http://"):
        allow_http = os.getenv("IMMICH_ALLOW_HTTP", "").lower() in ("true", "1")
        if not allow_http:
            logger.warning(
                "Credentials are configured but IMMICH_BASE_URL uses plain HTTP. "
                "This is insecure! Set IMMICH_ALLOW_HTTP=true to suppress this warning."
            )

    logger.debug(f"Requesting {method} {path}")
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.request(
                method, url, params=params, json=json_body, headers=headers
            )
        response.raise_for_status()
        logger.debug(f"Response {response.status_code} for {method} {path}")
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"HTTP error {exc.response.status_code} for {method} {path}: "
            f"{exc.response.text[:100]}"
        )
        raise ImmichAPIError(exc.response.status_code, exc.response.text) from exc
    except httpx.RequestError as exc:
        logger.error(f"Network error for {method} {path}: {str(exc)[:100]}")
        raise ImmichNetworkError(str(exc)) from exc

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    if _is_textual_content_type(content_type):
        return response.text

    payload_b64 = base64.b64encode(response.content).decode("ascii")
    return {
        "encoding": "base64",
        "content_type": content_type or "application/octet-stream",
        "size_bytes": len(response.content),
        "data": payload_b64,
    }


def _request_bytes(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    require_auth: bool = False,
    extra_headers: dict[str, Any] | None = None,
) -> tuple[bytes, dict[str, str]]:
    try:
        config = _get_config()
        url = f"{config['base_url']}{path}"
        headers = _build_headers(config, require_auth, extra_headers)
    except ValueError as exc:
        raise ImmichConfigError(str(exc)) from exc

    has_credentials = bool(config["api_key"] or config["api_token"])
    if has_credentials and config["base_url"].startswith("http://"):
        allow_http = os.getenv("IMMICH_ALLOW_HTTP", "").lower() in ("true", "1")
        if not allow_http:
            logger.warning(
                "Credentials are configured but IMMICH_BASE_URL uses plain HTTP. "
                "This is insecure! Set IMMICH_ALLOW_HTTP=true to suppress this warning."
            )

    logger.debug(f"Requesting binary payload {method} {path}")
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.request(
                method, url, params=params, json=json_body, headers=headers
            )
        response.raise_for_status()
        logger.debug(f"Binary response {response.status_code} for {method} {path}")
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"HTTP error {exc.response.status_code} for {method} {path}: "
            f"{exc.response.text[:100]}"
        )
        raise ImmichAPIError(exc.response.status_code, exc.response.text) from exc
    except httpx.RequestError as exc:
        logger.error(f"Network error for {method} {path}: {str(exc)[:100]}")
        raise ImmichNetworkError(str(exc)) from exc

    response_headers = {
        str(key).lower(): str(value) for key, value in response.headers.items()
    }
    return response.content, response_headers


def _probe(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    require_auth: bool = False,
) -> dict[str, Any]:
    try:
        config = _get_config()
        url = f"{config['base_url']}{path}"
        headers = _build_headers(config, require_auth)
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.request(
                method, url, params=params, json=json_body, headers=headers
            )
        return {
            "ok": response.status_code < 400,
            "status_code": response.status_code,
            "detail": response.text,
        }
    except httpx.RequestError as exc:
        return {"ok": False, "error": "Network error", "detail": str(exc)}
    except ValueError as exc:
        return {"ok": False, "error": "Configuration error", "detail": str(exc)}
