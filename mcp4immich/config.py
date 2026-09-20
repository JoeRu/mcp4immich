import os
from pathlib import Path
from typing import Any

from .constants import DEFAULT_BASE_URL


def get_mcp_settings() -> dict[str, Any]:
    host = os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port_raw = os.getenv("MCP_PORT", "8000").strip()
    log_level = os.getenv("MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO"
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ValueError("MCP_PORT must be an integer") from exc
    
    # Validate port range: 0 (auto-assign/test) or 1-65535
    if not (port == 0 or 1 <= port <= 65535):
        raise ValueError(
            f"MCP_PORT must be in range [0, 1-65535], got {port}. "
            f"Use 0 for auto-assign in test mode."
        )
    
    return {"host": host, "port": port, "log_level": log_level}


def get_transport_settings() -> tuple[str, str | None]:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    mount_path = os.getenv("MCP_MOUNT_PATH", "").strip() or None
    return transport, mount_path


def _get_config() -> dict[str, str]:
    base_url = os.getenv("IMMICH_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    api_key = os.getenv("IMMICH_API_KEY", "").strip()
    api_token = os.getenv("IMMICH_API_TOKEN", "").strip()
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        raise ValueError("IMMICH_BASE_URL must start with http:// or https://")
    return {"base_url": base_url, "api_key": api_key, "api_token": api_token}


def get_external_domain() -> str | None:
    """
    Get the external domain for web UI link building.
    
    Fallback chain:
    1. IMMICH_EXTERNAL_DOMAIN env var (if set)
    2. Discovered from GET /api/server-config externalDomain (if reachable)
    3. IMMICH_BASE_URL (if available)
    4. None (if all fallbacks fail)
    
    Returns:
        The external domain URL (e.g., https://immich.example.com) or None.
    """
    # Try environment variable first
    domain = os.getenv("IMMICH_EXTERNAL_DOMAIN", "").strip()
    if domain:
        domain = domain.rstrip("/")
        if not domain.startswith("http://") and not domain.startswith("https://"):
            raise ValueError("IMMICH_EXTERNAL_DOMAIN must start with http:// or https://")
        return domain
    
    # Try discovering from server config API
    try:
        from .http_client import _request
        payload = _request("GET", "/api/server-config")
        if isinstance(payload, dict):
            server_domain = payload.get("externalDomain") or payload.get("external_domain")
            if isinstance(server_domain, str) and server_domain.strip():
                server_domain = server_domain.strip().rstrip("/")
                return server_domain
    except Exception:
        pass
    
    # Fallback to IMMICH_BASE_URL
    try:
        config = _get_config()
        base_url = config.get("base_url", "").rstrip("/")
        if base_url:
            return base_url
    except Exception:
        pass
    
    return None


def get_usage_guide_path() -> str:
    base_dir = Path(__file__).resolve().parents[1]
    return str(base_dir / "docs" / "usage-guide.md")


def get_profile() -> str | None:
    """Get the configured access profile from IMMICH_PROFILE env var."""
    profile = os.getenv("IMMICH_PROFILE", "").strip().lower()
    if not profile:
        return None
    valid_profiles = {"read_only", "read_write", "full_scope"}
    if profile not in valid_profiles:
        raise ValueError(
            f"Invalid IMMICH_PROFILE: {profile}. "
            f"Must be one of: {', '.join(sorted(valid_profiles))}"
        )
    return profile


def profile_allows_write(profile: str | None) -> bool:
    """Check if the given profile allows write operations."""
    if profile is None:
        return True  # No profile restriction, rely on capability probes
    return profile in ("read_write", "full_scope")


def profile_allows_admin(profile: str | None) -> bool:
    """Check if the given profile allows admin operations."""
    if profile is None:
        return True  # No profile restriction, rely on capability probes
    return profile == "full_scope"


def get_download_asset_delivery_mode() -> str:
    """Return delivery mode for downloadAsset payloads."""
    mode = os.getenv("IMMICH_DOWNLOAD_ASSET_DELIVERY", "shared_link").strip().lower()
    valid_modes = {"inline_base64", "immich_link", "shared_link"}
    if mode not in valid_modes:
        raise ValueError(
            "IMMICH_DOWNLOAD_ASSET_DELIVERY must be one of: "
            f"{', '.join(sorted(valid_modes))}"
        )
    return mode
