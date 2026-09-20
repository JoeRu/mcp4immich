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
