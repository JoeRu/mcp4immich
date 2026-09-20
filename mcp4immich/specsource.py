"""Resolve the Immich OpenAPI spec: disk cache, then network, then vendored.

Startup must not depend on reaching raw.githubusercontent.com: an offline
restart used to leave the server with almost no tools, which looks exactly
like an Immich with no endpoints.
"""

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

VENDORED_DIR = Path(__file__).parent / "data"
DEFAULT_CACHE_DIR = Path(os.getenv("MCP4IMMICH_SPEC_CACHE", "/app/.cache/openapi"))


def _cache_file(cache_dir: Path, version_tag: str) -> Path:
    return cache_dir / f"immich-{version_tag}.json"


def _vendored_file(version_tag: str) -> Path:
    major = version_tag.lstrip("v").split(".")[0] or "3"
    return VENDORED_DIR / f"immich-openapi-{major}.json"


def resolve_spec(
    version_tag: str,
    fetch: Callable[[str], dict[str, Any]],
    cache_dir: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Return (spec, source) with source in {"cache", "network", "vendored"}."""
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cached = _cache_file(cache_dir, version_tag)

    if cached.is_file():
        try:
            return json.loads(cached.read_text()), "cache"
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Ignoring unreadable spec cache {cached}: {exc}")

    url = (
        "https://raw.githubusercontent.com/immich-app/immich/"
        f"{version_tag}/open-api/immich-openapi-specs.json"
    )
    try:
        spec = fetch(url)
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(spec))
        except OSError as exc:
            logger.warning(f"Could not write spec cache {cached}: {exc}")
        return spec, "network"
    except Exception as exc:
        logger.warning(f"Could not fetch spec for {version_tag} ({exc}); using vendored copy")

    vendored = _vendored_file(version_tag)
    spec = json.loads(vendored.read_text())
    vendored_version = spec.get("info", {}).get("version", "unknown")
    if not version_tag.lstrip("v").startswith(str(vendored_version)):
        logger.warning(
            f"Vendored spec is {vendored_version} but the server reports "
            f"{version_tag}; some endpoints may be missing or stale"
        )
    return spec, "vendored"
