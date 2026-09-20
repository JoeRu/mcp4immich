"""Risk classification for Immich operations — the single source of truth.

Everything downstream (tool annotations, the confirm gate, tool hiding)
derives from `classify()`. The fallback for an unrecognised DELETE is
DESTRUCTIVE, never WRITE: an endpoint we have never seen must fail closed.
"""

from enum import StrEnum

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH"})
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Operations that can destroy many originals at once, or affect other users.
#: An explicit list, not a shape heuristic: "DELETE without a trailing {id}"
#: would wrongly include membership removals such as DELETE /albums/{id}/assets.
#:
#: `POST /people/merge` is here too (added for C2): merging people is
#: irreversible and can silently reassign the identity of assets across the
#: whole library.
HIGH_RISK: frozenset[tuple[str, str]] = frozenset(
    {
        ("DELETE", "/assets"),
        ("DELETE", "/people"),
        ("POST", "/trash/empty"),
        ("POST", "/duplicates/resolve"),
        ("POST", "/people/merge"),
    }
)

#: Admin mutations verified by hand as the highest-stakes ones: restoring a
#: database backup overwrites the entire live database, and any DELETE under
#: /admin/ is already the DELETE fallback below. Everything else mutating
#: under /admin/ still fails closed to DESTRUCTIVE (see `classify`) --
#: this set exists only to put the single worst admin write in the smaller,
#: more-gated class alongside the DELETEs.
HIGH_RISK_ADMIN_PATHS: frozenset[str] = frozenset({"/admin/database-backups/start-restore"})


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

    if method == "POST" and path in HIGH_RISK_ADMIN_PATHS:
        return Risk.DESTRUCTIVE_ADMIN

    # C2 fail-closed rule: the block above only ever caught DELETE under
    # /admin/ plus a hand-picked list, which left every other admin mutation
    # -- POST /admin/database-backups/start-restore (before the line above),
    # PUT /admin/config, POST /admin/maintenance, POST /admin/auth/unlink-all,
    # POST /admin/users, ... -- classifying as ordinary WRITE and executing
    # with no confirmation at all. Any mutating verb under /admin/ is now at
    # least DESTRUCTIVE, in the same spirit as the DELETE fallback below: an
    # admin mutation we have not explicitly reviewed into DESTRUCTIVE_ADMIN
    # must still never be silently classified as safe.
    if method in MUTATING_METHODS and path.startswith("/admin/"):
        return Risk.DESTRUCTIVE

    if method == "DELETE":
        return Risk.DESTRUCTIVE

    if method in WRITE_METHODS:
        return Risk.WRITE

    return Risk.READ
