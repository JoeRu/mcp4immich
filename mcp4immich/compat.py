"""Immich endpoints that moved between major versions.

Only endpoints that actually moved belong here. `/api/server-config` became
`/api/server/config` in Immich 3.x; calling the old path on a 3.x server
returns 404, which silently disabled external-domain discovery and made every
web_url point at the internal base URL.
"""

import logging

logger = logging.getLogger(__name__)

_ENDPOINTS: dict[str, dict[int, str]] = {
    "server_config": {2: "/api/server-config", 3: "/api/server/config"},
}


def endpoint(name: str, major: int) -> str:
    by_major = _ENDPOINTS[name]
    if major in by_major:
        return by_major[major]
    newest = max(by_major)
    if major > newest:
        logger.info(f"Immich major {major} is newer than known; using the {newest} path for {name}")
        return by_major[newest]
    oldest = min(by_major)
    return by_major[oldest]
