import logging
import os
from functools import lru_cache
from typing import Any

from .config import _get_config
from .http_client import _probe, _request

logger = logging.getLogger(__name__)


def _format_probe_failure(method: str, path: str, probe: dict[str, Any]) -> str:
    status_code = probe.get("status_code")
    if isinstance(status_code, int):
        return f"Capability check failed (HTTP {status_code}) for {method} {path}"
    error = probe.get("error")
    detail = probe.get("detail")
    if error and detail:
        return f"Capability check failed: {error} ({detail})"
    if error:
        return f"Capability check failed: {error}"
    if detail:
        return f"Capability check failed: {detail}"
    return "Immich server error during capability check"


@lru_cache
def _discover_user_profile() -> dict[str, Any]:
    try:
        profile = _request("GET", "/api/users/me", require_auth=True)
        if isinstance(profile, dict):
            return profile
    except Exception:
        pass
    return {}


@lru_cache
def _discover_capabilities() -> dict[str, dict[str, str | bool]]:
    logger.debug("Discovering API capabilities")
    capabilities: dict[str, dict[str, str | bool]] = {
        "get_current_user": {"allowed": False, "reason": "Not checked"}
    }
    config = _get_config()
    if not (config["api_key"] or config["api_token"]):
        logger.debug("No credentials configured; capabilities unavailable")
        capabilities["get_current_user"]["reason"] = (
            "Missing IMMICH_API_KEY or IMMICH_API_TOKEN"
        )
        return capabilities

    probe = _probe("GET", "/api/users/me", require_auth=True)
    if probe.get("ok"):
        logger.debug("Authentication successful; get_current_user allowed")
        capabilities["get_current_user"]["allowed"] = True
        capabilities["get_current_user"]["reason"] = "Allowed"
        return capabilities

    status_code = probe.get("status_code")
    if status_code in (401, 403):
        logger.debug(f"Authorization denied for get_current_user (HTTP {status_code})")
        capabilities["get_current_user"]["reason"] = (
            "API key/token lacks permission for /api/users/me"
        )
        return capabilities

    logger.warning(f"Capability check failed for get_current_user: {probe}")
    capabilities["get_current_user"]["reason"] = _format_probe_failure(
        "GET", "/api/users/me", probe
    )
    return capabilities


@lru_cache
def _discover_write_capability() -> dict[str, str | bool]:
    logger.debug("Discovering write capability")
    method, path = _write_probe_settings()
    logger.debug(f"Write probe: {method} {path}")

    probe = _probe(method, path, require_auth=True)
    if probe.get("ok"):
        logger.debug("Write capability allowed")
        return {"configured": True, "allowed": True, "reason": "Allowed"}

    status_code = probe.get("status_code")
    if status_code in (401, 403):
        logger.debug(f"Write capability denied (HTTP {status_code})")
        return {
            "configured": True,
            "allowed": False,
            "reason": f"API key/token lacks permission for {method} {path}",
        }

    if status_code == 400:
        logger.debug("Write probe returned validation error (treating as allowed)")
        return {
            "configured": True,
            "allowed": True,
            "reason": "Allowed (write probe returned validation error)",
        }

    logger.warning(f"Write capability check failed: {probe}")
    return {
        "configured": True,
        "allowed": False,
        "reason": _format_probe_failure(method, path, probe),
    }


def _write_probe_settings() -> tuple[str, str]:
    method = os.getenv("IMMICH_WRITE_PROBE_METHOD", "POST").strip().upper()
    if not method:
        method = "POST"
    path = os.getenv("IMMICH_WRITE_PROBE_PATH", "").strip()
    if not path:
        path = "/api/assets"
    return method, path
