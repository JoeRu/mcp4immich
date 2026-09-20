import json
from pathlib import Path

import pytest

from mcp4immich.risk import Risk, classify

SPEC = json.loads((Path("mcp4immich/data/immich-openapi-3.json")).read_text())


@pytest.mark.parametrize(
    "method,path,expected",
    [
        ("GET", "/assets", Risk.READ),
        ("GET", "/search/suggestions", Risk.READ),
        ("POST", "/search/metadata", Risk.WRITE),
        ("PUT", "/assets/{id}", Risk.WRITE),
        ("POST", "/trash/restore", Risk.WRITE),
        ("DELETE", "/albums/{id}", Risk.DESTRUCTIVE),
        ("DELETE", "/albums/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/memories/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/tags/{id}/assets", Risk.DESTRUCTIVE),
        ("DELETE", "/stacks", Risk.DESTRUCTIVE),
        ("DELETE", "/assets", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/people", Risk.DESTRUCTIVE_ADMIN),
        ("POST", "/trash/empty", Risk.DESTRUCTIVE_ADMIN),
        ("POST", "/duplicates/resolve", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/admin/users/{id}", Risk.DESTRUCTIVE_ADMIN),
        ("DELETE", "/admin/database-backups", Risk.DESTRUCTIVE_ADMIN),
    ],
)
def test_classifies_known_operations(method, path, expected):
    assert classify(method, path) is expected


def test_method_case_does_not_matter():
    assert classify("delete", "/albums/{id}") is Risk.DESTRUCTIVE


def test_every_delete_in_the_spec_is_destructive():
    """A future Immich release must not be able to add an unguarded delete."""
    unguarded = [
        path
        for path, ops in SPEC["paths"].items()
        if "delete" in ops
        and classify("DELETE", path) not in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)
    ]
    assert unguarded == []


def test_membership_removals_are_not_admin_class():
    """Removing assets from an album/tag/memory leaves the assets in place."""
    for path in (
        "/albums/{id}/assets",
        "/memories/{id}/assets",
        "/tags/{id}/assets",
        "/shared-links/{id}/assets",
    ):
        assert classify("DELETE", path) is Risk.DESTRUCTIVE


# --- C2: non-DELETE admin mutations must not be plain WRITE ---------------
#
# Before the fix, the admin rule matched only DELETE under /admin/, so
# POST /admin/database-backups/start-restore (overwrites the live database
# from a backup) classified as ordinary WRITE and executed with no
# confirmation. Fail closed: ANY mutating verb under /admin/ is at least
# DESTRUCTIVE, and the two verified-highest-risk operations are
# DESTRUCTIVE_ADMIN specifically.


def test_start_restore_and_people_merge_are_destructive_admin():
    """These two are irreversible and affect the whole library / all users,
    so they must sit in the smallest, most-gated class, not merely
    DESTRUCTIVE."""
    assert classify("POST", "/admin/database-backups/start-restore") is Risk.DESTRUCTIVE_ADMIN
    assert classify("POST", "/people/merge") is Risk.DESTRUCTIVE_ADMIN


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/admin/auth/unlink-all"),
        ("PUT", "/admin/config"),
        ("POST", "/admin/maintenance"),
        ("POST", "/admin/users"),
        ("PUT", "/admin/users/{id}"),
    ],
)
def test_other_admin_mutations_are_no_longer_plain_write(method, path):
    assert classify(method, path) not in (Risk.READ, Risk.WRITE)


def test_no_admin_mutation_in_the_spec_is_read_or_write():
    """Spec-wide: any POST/PUT/PATCH/DELETE under /admin/ must be gated --
    the admin rule targeted only DELETE before this fix, so e.g.
    POST /admin/database-backups/start-restore slipped through as WRITE."""
    unguarded = [
        (method.upper(), path)
        for path, ops in SPEC["paths"].items()
        if path.startswith("/admin/")
        for method in ops
        if method.upper() in ("POST", "PUT", "PATCH", "DELETE")
        and classify(method.upper(), path) not in (Risk.DESTRUCTIVE, Risk.DESTRUCTIVE_ADMIN)
    ]
    assert unguarded == []
