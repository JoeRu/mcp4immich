"""Risk classification for Immich operations — the single source of truth.

Everything downstream (tool annotations, the confirm gate, tool hiding)
derives from `classify()`. The fallback for an unrecognised DELETE is
DESTRUCTIVE, never WRITE: an endpoint we have never seen must fail closed.
"""

from enum import StrEnum

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})

#: Operations that can destroy many originals at once, or affect other users.
#: An explicit list, not a shape heuristic: "DELETE without a trailing {id}"
#: would wrongly include membership removals such as DELETE /albums/{id}/assets.
HIGH_RISK: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", "/assets"),
        ("DELETE", "/people"),
        ("POST", "/trash/empty"),
        ("POST", "/duplicates/resolve"),
    }
)


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"
    DESTRUCTIVE_ADMIN = "destructive_admin"


def classify(method: str, path: str) -> Risk:
    """Classify one OpenAPI operation by method and spec path (no base prefix)."""
    method = method.upper()
    path = "/" + path.lstrip("/")

    if method == "DELETE" and path.startswith("/admin/"):
        return Risk.DESTRUCTIVE_ADMIN

    if (method, path) in HIGH_RISK:
        return Risk.DESTRUCTIVE_ADMIN

    if method == "DELETE":
        return Risk.DESTRUCTIVE

    if method in WRITE_METHODS:
        return Risk.WRITE

    return Risk.READ
